"""NumPy-only dense integer-equivalent oracle for artifact replay.

Float64 multiply/add is exact for these bounded integer accumulators (<2**53).
The original capture qualification also used an independently checked PyTorch
float64 convolution. This implementation removes PyTorch from artifact setup.
"""
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.experiments.paper2_conventional_comparison_v1.comparison import WEIGHTS,Rect,fused_region
from src.hardware.experiment133.reference_sparse_distilled_same_bitstream_133 import parse_trained_package

def golden():
 model=parse_trained_package(WEIGHTS)
 y,x,c=np.indices((360,640,3),dtype=np.int32)
 image=((17*y+29*x+43*c+51)%256-128).astype(np.int8)
 activation=image.astype(np.float64)
 for layer in range(3):
  weight=model.weights[layer].astype(np.float64);bias=model.biases[layer].astype(np.float64)
  padded=np.pad(activation,((1,1),(1,1),(0,0)))
  windows=np.lib.stride_tricks.sliding_window_view(padded,(3,3),axis=(0,1))
  out=np.empty((360,640,len(bias)),dtype=np.float64)
  for row in range(0,360,24):
   value=np.einsum('yxckl,ockl->yxo',windows[row:row+24],weight,optimize=True)+bias
   value=np.sign(value)*np.floor((np.abs(value)+128)/256)
   if layer<2:value=np.maximum(value,0)
   out[row:row+24]=np.clip(value,-128,127)
  activation=out
 packed=activation.astype(np.int8).reshape(360,640,3,2,2).transpose(0,3,1,4,2).reshape(720,1280,3)
 # A separately implemented INT64 halo oracle checks borders and an interior.
 for box in (Rect(0,0,3,4),Rect(120,256,124,260),Rect(357,636,360,640)):
  exact=fused_region(image,model,box).reshape(box.y1-box.y0,box.x1-box.x0,3,2,2).transpose(0,3,1,4,2).reshape(2*(box.y1-box.y0),2*(box.x1-box.x0),3)
  assert np.array_equal(exact,packed[2*box.y0:2*box.y1,2*box.x0:2*box.x1])
 words=packed.astype(np.uint8).astype(np.uint32)
 return words[:,:,0]|(words[:,:,1]<<8)|(words[:,:,2]<<16)
