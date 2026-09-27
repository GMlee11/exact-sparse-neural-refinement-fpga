"""Independent frozen oracle for Experiment 133.

Consumes only the accepted synthetic formula and hash-pinned pre-131 trained
weights. It deliberately has no Experiment 131/132 source dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from pathlib import Path
import numpy as np
import yaml

EXPERIMENT_ID = "sparse_distilled_same_bitstream_mechanisms_133_v1"
CONFIG_SHA256 = "cbba83253db0542d14773d7db15cff189a485fdeff9644e22cded0b0277cd889"
PROTOCOL_SHA256 = "113132414fc0a0761a4ab92bd05f0581ddafd2fe93da2e4e8e7efc96a9bd45bb"
WEIGHTS_SHA256 = "cc1a67ee659447a80252c97064ed7bc50826b40649ebf3c8399ef189ba692029"
FNV_OFFSET, FNV_PRIME = 0x811C9DC5, 16_777_619
HEIGHT, WIDTH, OUTPUT_HEIGHT, OUTPUT_WIDTH, FEATURES = 72, 128, 144, 256, 24
MASKS = (0x000000,0xFFFFFF,0x000001,0x000800,0x800000,0x000081,
         0x555555,0x080808,0x00FF00,0x810081,0x181800,0xA55AA5)

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_contract(repo_root: Path) -> dict:
    config = repo_root / "configs/sparse_distilled_same_bitstream_mechanisms_133_v1.yaml"
    protocol = repo_root / "docs/paper2_experiment133_distilled_same_bitstream_protocol.md"
    if sha256(config) != CONFIG_SHA256 or sha256(protocol) != PROTOCOL_SHA256:
        raise ValueError("frozen Experiment 133 preregistration hash mismatch")
    parsed = yaml.safe_load(config.read_text(encoding="utf-8"))
    if tuple(int(v, 16) for v in parsed["workload"]["masks_hex_in_order"]) != MASKS:
        raise ValueError("frozen mask order mismatch")
    return parsed

def synthetic_input() -> np.ndarray:
    y=np.arange(HEIGHT,dtype=np.int32)[:,None,None]
    x=np.arange(WIDTH,dtype=np.int32)[None,:,None]
    c=np.arange(3,dtype=np.int32)[None,None,:]
    return (((y*17+x*29+c*43+0x33)%256)-128).astype(np.int8)

def input_packet_words() -> np.ndarray:
    image=synthetic_input().astype(np.uint8)
    rows=tuple(range(0,27))+tuple(range(21,51))+tuple(range(45,72))
    words=np.asarray([int(image[y,x,0])|(int(image[y,x,1])<<8)|(int(image[y,x,2])<<16)
                      for y in rows for x in range(WIDTH)],dtype=np.uint32)
    if len(words)!=10_752: raise AssertionError("input packet is not 10,752 words")
    return words

@dataclass(frozen=True)
class TrainedModel:
    weights: tuple[np.ndarray,np.ndarray,np.ndarray]
    biases: tuple[np.ndarray,np.ndarray,np.ndarray]

def _signed_hex(value: str,bits: int)->int:
    raw=int(value,16)
    return raw-(1<<bits) if raw&(1<<(bits-1)) else raw

def parse_trained_package(path: Path)->TrainedModel:
    if sha256(path)!=WEIGHTS_SHA256: raise ValueError("trained package hash mismatch")
    text=path.read_text(encoding="utf-8")
    rows={}
    for index,literal in re.findall(r"^\s*(\d+): trained_weight_row = \{([^}]+)\};",text,re.MULTILINE):
        values=re.findall(r"8'sh([0-9A-Fa-f]{2})",literal)
        if len(values)!=9: raise ValueError(f"weight row {index} is malformed")
        rows[int(index)]=[_signed_hex(v,8) for v in reversed(values)]
    bias={int(i):_signed_hex(v,32) for i,v in re.findall(
        r"^\s*(\d+): trained_bias_flat = 32'sh([0-9A-Fa-f]{8});",text,re.MULTILINE)}
    if len(rows)!=936 or len(bias)!=60:
        raise ValueError(f"unexpected package shape rows={len(rows)} biases={len(bias)}")
    specs=((24,3,0,0),(24,24,72,24),(12,24,648,48)); weights=[]; biases=[]
    for outputs,inputs,row0,bias0 in specs:
        layer=np.empty((outputs,inputs,3,3),dtype=np.int8)
        for o in range(outputs):
            for i in range(inputs):
                layer[o,i]=np.asarray(rows[row0+o*inputs+i],dtype=np.int8).reshape(3,3)
        weights.append(layer); biases.append(np.asarray([bias[bias0+o] for o in range(outputs)],dtype=np.int32))
    return TrainedModel(tuple(weights),tuple(biases)) # type: ignore[arg-type]

def round_shift_ties_away(values: np.ndarray,shift: int=8)->np.ndarray:
    wide=values.astype(np.int64,copy=False); rounded=(np.abs(wide)+(1<<(shift-1)))>>shift
    return np.where(wide<0,-rounded,rounded)

def conv3x3(image: np.ndarray,weights: np.ndarray,bias: np.ndarray,relu: bool)->np.ndarray:
    height,width,inputs=image.shape; outputs=weights.shape[0]
    if int(np.max(np.abs(bias.astype(np.int64))))+inputs*9*128*128>=2**31:
        raise OverflowError("INT32 overflow bound failed")
    padded=np.pad(image.astype(np.int64),((1,1),(1,1),(0,0)))
    result=np.empty((height,width,outputs),dtype=np.int8)
    for o in range(outputs):
        acc=np.full((height,width),int(bias[o]),dtype=np.int64)
        for i in range(inputs):
            for ky in range(3):
                for kx in range(3):
                    acc += padded[ky:ky+height,kx:kx+width,i]*int(weights[o,i,ky,kx])
        value=round_shift_ties_away(acc)
        if relu: value=np.maximum(value,0)
        result[:,:,o]=np.clip(value,-128,127).astype(np.int8)
    return result

def _bicubic(image: np.ndarray)->np.ndarray:
    phases=((-9,67,225,-27),(-27,225,67,-9)); output=np.empty((144,256,3),dtype=np.int8)
    for oy in range(144):
        cy=oy//2; fy=cy+(-2 if oy%2==0 else -1); wy=phases[oy&1]
        for ox in range(256):
            cx=ox//2; fx=cx+(-2 if ox%2==0 else -1); wx=phases[ox&1]
            for channel in range(3):
                total=sum(int(image[min(max(fy+ky,0),71),min(max(fx+kx,0),127),channel])*wy[ky]*wx[kx]
                          for ky in range(4) for kx in range(4))
                output[oy,ox,channel]=np.int8(np.clip(int(round_shift_ties_away(np.asarray(total),16)),-128,127))
    return output

def dense_output(model: TrainedModel)->np.ndarray:
    image=synthetic_input(); c1=conv3x3(image,model.weights[0],model.biases[0],True)
    c2=conv3x3(c1,model.weights[1],model.biases[1],True)
    c3=conv3x3(c2,model.weights[2],model.biases[2],False)
    residual=np.empty((144,256,3),dtype=np.int8)
    for y in range(72):
        for x in range(128):
            for sy in range(2):
                for sx in range(2):
                    for ch in range(3): residual[2*y+sy,2*x+sx,ch]=c3[y,x,ch*4+sy*2+sx]
    return np.clip(_bicubic(image).astype(np.int16)+residual.astype(np.int16),-128,127).astype(np.int8)

def output_words(output: np.ndarray)->np.ndarray:
    raw=output.astype(np.uint8)
    return (raw[:,:,0].astype(np.uint32)|(raw[:,:,1].astype(np.uint32)<<8)|
            (raw[:,:,2].astype(np.uint32)<<16)).reshape(-1)

def selected_coordinate(y:int,x:int,mask:int)->bool:
    return bool((mask>>((y//48)*8+(x//32)))&1)

def selected_words(words:np.ndarray,mask:int)->np.ndarray:
    selected=np.asarray([int(words[y*256+x]) for y in range(144) for x in range(256)
                         if selected_coordinate(y,x,mask)],dtype=np.uint32)
    if len(selected)!=mask.bit_count()*1536: raise AssertionError("selected length mismatch")
    return selected

def fnv1a32(words:np.ndarray)->int:
    value=FNV_OFFSET
    for word in words: value=((value^int(word))*FNV_PRIME)&0xFFFFFFFF
    return value

def destination_buffer(words:np.ndarray,mask:int,sentinel:int)->bytes:
    result=bytearray([sentinel]*110_592)
    for y in range(144):
        for x in range(256):
            if selected_coordinate(y,x,mask):
                word=int(words[y*256+x]); offset=(y*256+x)*3
                result[offset:offset+3]=bytes((word&255,(word>>8)&255,(word>>16)&255))
    return bytes(result)

def requested_sites(mask:int,band:int)->set[tuple[int,int]]:
    return {(y,x) for tile in range(8) if (mask>>(band*8+tile))&1
            for y in range(band*24,(band+1)*24) for x in range(tile*16,(tile+1)*16)}

def dilate(sites:set[tuple[int,int]],radius:int)->set[tuple[int,int]]:
    return {(y+dy,x+dx) for y,x in sites for dy in range(-radius,radius+1)
            for dx in range(-radius,radius+1) if 0<=y+dy<72 and 0<=x+dx<128}

def rectangle(sites:set[tuple[int,int]],radius:int)->set[tuple[int,int]]:
    if not sites: return set()
    ys,xs=zip(*sites)
    return {(y,x) for y in range(max(0,min(ys)-radius),min(71,max(ys)+radius)+1)
            for x in range(max(0,min(xs)-radius),min(127,max(xs)+radius)+1)}

def workset(mask:int,band:int,radius:int,exact:bool)->set[tuple[int,int]]:
    sites=requested_sites(mask,band); return dilate(sites,radius) if exact else rectangle(sites,radius)

def mode_counters(mask:int,exact:bool,retained:bool)->dict:
    sets=[[workset(mask,b,r,exact) for b in range(3)] for r in (2,1,0)]
    reuse=[0,0,0]
    if retained:
        for layer in (0,1): reuse[layer]=sum(len(sets[layer][b]&sets[layer][b+1]) for b in (0,1))
    active=[sum(map(len,s))-reuse[i] for i,s in enumerate(sets)]
    bypass=[10_752-sum(map(len,s)) for s in sets]
    reused=(reuse[0]+reuse[1])*24
    suppressed=sum(len(sets[1][b]&sets[1][b+1]) for b in (0,1)) if retained else 0
    return {"conv1_active_positions":active[0],"conv2_active_positions":active[1],
            "conv3_active_positions":active[2],"bypassed_positions":dict(zip(("conv1","conv2","conv3"),bypass)),
            "input_axis_words":10_752,"output_axis_words":mask.bit_count()*1536,
            "internal_state_reads":reused,"internal_state_writes":reused,"halo_replay_positions":1536,
            "halo_suppressed_positions":suppressed,"reused_activations":reused,"segment_launches":3}

def publication_outcome(case_index:int,guarded:bool,words:np.ndarray)->dict:
    if case_index not in range(6): raise ValueError("publication case must be 0..5")
    mask=0xA55AA5; selected=selected_words(words,mask)
    pub=guarded and case_index==0; quarantine=not guarded
    public=destination_buffer(words,mask,0xA5) if pub else bytes([0xA5])*110_592
    qbuf=destination_buffer(words,mask,0x5A) if quarantine else bytes([0x5A])*110_592
    return {"public_transactions":int(pub),"quarantine_transactions":int(quarantine),
            "public_sequence_delta":int(pub),"quarantine_sequence_delta":int(quarantine),
            "selected_words":len(selected),"selected_bytes":len(selected)*3,"selected_checksum":fnv1a32(selected),
            "public_sha256":hashlib.sha256(public).hexdigest(),"quarantine_sha256":hashlib.sha256(qbuf).hexdigest()}
