/* Common-image engineering/confirmation campaign. No UART/JTAG in timed work.
 * Timed boundary: region planning -> dependency packing -> DMA/compute ->
 * private selected-residual scatter -> validated software publication.
 * This is not rendering, residual addition, or complete display service. */
#include <stdint.h>
#include <string.h>
#include "xil_cache.h"
#include "xil_io.h"
#include "xil_mmu.h"
#include "xil_printf.h"
#include "xuartps.h"
#include "xtime_l.h"
#include "roi_campaign_masks.h"

#define CFG 0x41200000U
#define RSP 0x41210000U
#define DMA 0x40400000U
#define TX ((uint32_t*)0x01000000U)
#define RX ((uint32_t*)0x02000000U)
static const uint32_t *frame_input;
#define INPUT frame_input
#define FRAME_BANK ((const uint32_t*)0x18000000U)
#define LAUNCH ((volatile uint32_t*)0x05100000U)
#define DENSE ((uint32_t*)0x17000000U)
#define FRAME_WORDS 230400U
#define DENSE_WORDS 921600U
#define PRIVATE private_target
#define MAIL ((volatile uint32_t*)0x05000000U)
#define ARCHIVE ((uint32_t*)0x06000000U)
#define ARCHIVE_WORDS 0x04000000U /* Exclusive end0x16000000 <512MiB DDR. */
#define TIMEOUT_TICKS (30ULL*COUNTS_PER_SECOND)
#define IOC (1U<<12)
#define DMA_ERRORS 0x770U
#define RECORD_WORDS 28U
#ifndef ROI_REPEATS
#define ROI_REPEATS 3U
#endif
#define REPEATS ROI_REPEATS
#define MODES 3U
#ifndef ROI_CACHE_ENABLED
#define ROI_CACHE_ENABLED 1
#endif
typedef struct {uint64_t mask;unsigned x,y,w,h;} Region;
static Region regions[60];
static uint32_t archive_used,record_count,frame_id;
static uint32_t *private_target=(uint32_t*)0x04000000U;
static unsigned private_slot;
static unsigned active_condition,launch_kind,repeat_base,launch_ordinal,operation,initial_bank;
static unsigned preparation_count;
void __attribute__((weak)) _init(void){}
void __attribute__((weak)) _fini(void){}
static uint64_t now(void){XTime t;XTime_GetTime(&t);return t;}
static void wr(unsigned a,uint32_t v){Xil_Out32(CFG,0);Xil_Out32(CFG+8,v);Xil_Out32(CFG,(a&255)|256);Xil_Out32(CFG,0);}
static uint32_t rd(unsigned a){Xil_Out32(CFG,(a&255)<<16);uint32_t v=Xil_In32(RSP);Xil_Out32(CFG,0);return v;}
static uint32_t status(void){return Xil_In32(RSP+8);}
static unsigned bit(uint64_t m,unsigned r,unsigned c){return (unsigned)((m>>(r*10+c))&1ULL);}
static unsigned pop(uint64_t m){unsigned n=0;while(m){m&=m-1;n++;}return n;}
static unsigned maxu(unsigned a,unsigned b){return a>b?a:b;}
static unsigned minu(unsigned a,unsigned b){return a<b?a:b;}
static Region expanded(unsigned x,unsigned y,unsigned w,unsigned h,uint64_t m){
 Region q;unsigned x1=minu(640,x+w+3),y1=minu(360,y+h+3);q.x=x>3?x-3:0;q.y=y>3?y-3:0;q.w=x1-q.x;q.h=y1-q.y;q.mask=m;return q;}
/* Conventional horizontal runs merged vertically only for equal column spans. */
static unsigned plan(uint64_t mask,unsigned mode){
 unsigned n=0,r,c,k,x0,x1,y0=360,y1=0;uint64_t used=0;
 if(!mask)return 0;
 if(mode==0){regions[0]=(Region){mask,0,0,640,360};return 1;}
 if(mode==1){x0=640;x1=0;for(k=0;k<60;k++)if(mask&(1ULL<<k)){x0=minu(x0,(k%10)*64);x1=maxu(x1,(k%10+1)*64);y0=minu(y0,(k/10)*60);y1=maxu(y1,(k/10+1)*60);}regions[0]=expanded(x0,y0,x1-x0,y1-y0,mask);return 1;}
 for(r=0;r<6;r++)for(c=0;c<10;c++)if(bit(mask&~used,r,c)){
  unsigned end=c+1,bottom=r+1;while(end<10 && bit(mask&~used,r,end))end++;
  while(bottom<6){unsigned okay=1;
   if((c && bit(mask&~used,bottom,c-1)) || (end<10 && bit(mask&~used,bottom,end)))okay=0;
   for(k=c;k<end;k++)if(!bit(mask&~used,bottom,k))okay=0;
   if(!okay)break;bottom++;
  }
  uint64_t owned=0;unsigned rr,cc;for(rr=r;rr<bottom;rr++)for(cc=c;cc<end;cc++)owned|=1ULL<<(rr*10+cc);
  used|=owned;regions[n++]=expanded(c*64,r*60,(end-c)*64,(bottom-r)*60,owned);
 }
 return n;
}
/* Merge selected halo intervals per scanline. Ordinary full-raster input
 * packing uses exactly this routine too; it is not charged a naive pixel scan. */
static unsigned pack(const Region*q){
 unsigned y,c,r,count=0;
 for(y=q->y;y<q->y+q->h;y++){
  unsigned pending=0,lo=0,hi=0;
  for(c=0;c<10;c++){
   unsigned needed=0;
   for(r=0;r<6;r++)if(bit(q->mask,r,c) && y+3>=r*60 && y<(r+1)*60+3)needed=1;
   if(needed){unsigned a=maxu(q->x,c*64>3?c*64-3:0),b=minu(q->x+q->w,minu(640,(c+1)*64+3));
    if(pending && a>hi){memcpy(TX+count,INPUT+y*640+lo,(hi-lo)*4);count+=hi-lo;pending=0;}
    if(!pending){lo=a;hi=b;pending=1;}else hi=maxu(hi,b);
   }
  }
  if(pending){memcpy(TX+count,INPUT+y*640+lo,(hi-lo)*4);count+=hi-lo;}
 }
 return count;
}
static unsigned scatter(const Region*q){
 unsigned y,c,count=0;
 for(y=q->y*2;y<(q->y+q->h)*2;y++)for(c=0;c<10;c++)if(bit(q->mask,y/120,c)){
  memcpy(PRIVATE+y*1280+c*128,RX+count,128*4);count+=128;
 }
 return count;
}
static int dma_init(void){
 uint64_t start=now();Xil_Out32(DMA,4);Xil_Out32(DMA+0x30,4);
 while((Xil_In32(DMA)|Xil_In32(DMA+0x30))&4)if(now()-start>TIMEOUT_TICKS)return -1;
 Xil_Out32(DMA+4,0xffffffff);Xil_Out32(DMA+0x34,0xffffffff);Xil_Out32(DMA,1);Xil_Out32(DMA+0x30,1);return 0;
}
static void dma_start(unsigned nin,unsigned nout){
 if(ROI_CACHE_ENABLED){Xil_DCacheFlushRange((UINTPTR)TX,nin*4);Xil_DCacheFlushRange((UINTPTR)RX,nout*4);}
 Xil_Out32(DMA+4,0xffffffff);Xil_Out32(DMA+0x34,0xffffffff);
 Xil_Out32(DMA+0x48,(uint32_t)RX);Xil_Out32(DMA+0x58,nout*4);
 Xil_Out32(DMA+0x18,(uint32_t)TX);Xil_Out32(DMA+0x28,nin*4);
}
static int wait_region(unsigned final){
 uint64_t start=now();for(;;){uint32_t a=Xil_In32(DMA+4),b=Xil_In32(DMA+0x34),s=status();
  if(((a|b)&DMA_ERRORS) || (s&16) || ((s&2)&&!(s&4)))return -1;
  if((a&IOC)&&(b&IOC)&&((final&&(s&4))||(!final&&(s&8))))return 0;
  if(now()-start>TIMEOUT_TICKS)return -2;
 }
}
static void word64(volatile uint32_t*p,uint64_t v){p[0]=(uint32_t)v;p[1]=(uint32_t)(v>>32);}
static uint32_t checksum(uint64_t mask){
 uint32_t h=0x811c9dc5U;unsigned y,c,k;
 for(y=0;y<720;y++)for(c=0;c<10;c++)if(bit(mask,y/120,c))for(k=0;k<128;k++){h^=PRIVATE[y*1280+c*128+k];h*=16777619U;}
 return h;
}
static unsigned save_bytes(uint64_t mask){
 unsigned y,c,start=archive_used,n=pop(mask)*15360;
 if(archive_used+n>ARCHIVE_WORDS)return 0xffffffffU;
 for(y=0;y<720;y++)for(c=0;c<10;c++)if(bit(mask,y/120,c)){
  memcpy(ARCHIVE+archive_used,PRIVATE+y*1280+c*128,128*4);archive_used+=128;
 }
 return start;
}
static void publish_flush(uint64_t mask){
 if(ROI_CACHE_ENABLED){unsigned y,c;for(y=0;y<720;y++)for(c=0;c<10;c++)if(bit(mask,y/120,c))Xil_DCacheFlushRange((UINTPTR)(PRIVATE+y*1280+c*128),128*4);}
}
static int run(unsigned case_no,unsigned mode,unsigned repeat,unsigned record){
 uint64_t mask=ROI_MASKS[case_no];unsigned n,i,inputs=0,outputs=0;int rc=0;
 uint64_t start=now(),planned,packed_ticks=0,dma_ticks=0,scatter_ticks=0,finish;
 /* The benchmark consumer completes validation/archival before the next call.
  * Keep the currently published bank intact throughout the next request. */
 private_slot=(MAIL[7]&1U)^1U;private_target=(uint32_t*)(0x04000000U+private_slot*0x00400000U);
 n=plan(mask,mode);planned=now();wr(3,4);if(dma_init())rc=-3;
 wr(0,(uint32_t)mask);wr(1,(uint32_t)(mask>>32));wr(16,++frame_id);wr(17,0);wr(18,0);wr(3,1);
 for(i=0;i<n && !rc;i++){
  Region*q=&regions[i];uint64_t mark=now();unsigned nin=pack(q),nout=pop(q->mask)*15360;packed_ticks+=now()-mark;
  wr(2,nin);wr(39,q->x|(q->y<<16));wr(40,q->w|(q->h<<16));wr(41,(uint32_t)q->mask);wr(42,(uint32_t)(q->mask>>32));wr(43,i+1==n);
  mark=now();wr(3,16);dma_start(nin,nout);rc=wait_region(i+1==n);dma_ticks+=now()-mark;
  if(!rc && (rd(6)!=nin || rd(8)!=nout))rc=-4;
  if(!rc){mark=now();if(ROI_CACHE_ENABLED)Xil_DCacheInvalidateRange((UINTPTR)RX,nout*4);if(scatter(q)!=nout)rc=-5;scatter_ticks+=now()-mark;inputs+=nin;outputs+=nout;}
 }
 if(!n){uint64_t mark=now();while(!(status()&2) && now()-mark<TIMEOUT_TICKS){} }
 if(!rc && (!(status()&4) || rd(19)!=frame_id || rd(44)!=pop(mask)*15360))rc=-6;
 if(!rc){publish_flush(mask);__asm__ volatile("dmb sy" ::: "memory");MAIL[7]=(frame_id<<1)|private_slot;} /* Atomic frame+bank token; metadata-validated, not a per-request numerical oracle. */
 finish=now();
 uint32_t s=status(),cyc=rd(5),sum=rc?0:checksum(mask),offset=0xffffffffU;
 if(!rc && sum!=ROI_EXPECTED_FNV[case_no])rc=-8;
 if(!rc && rd(49)!=(active_condition==2?3U:0U))rc=-9;
 if(record && repeat==0 && !rc){offset=save_bytes(mask);if(offset==0xffffffffU)rc=-7;}
 if(record || rc){volatile uint32_t*p=MAIL+32+record_count*RECORD_WORDS;
  p[0]=case_no;p[1]=mode;p[2]=repeat;p[3]=(uint32_t)rc;p[4]=n;p[5]=inputs;p[6]=outputs;p[7]=s;
  word64(p+8,finish-start);word64(p+10,planned-start);word64(p+12,packed_ticks);word64(p+14,dma_ticks);word64(p+16,scatter_ticks);
  p[18]=cyc;p[19]=sum;p[20]=offset;p[21]=pop(mask)*15360;p[22]=frame_id;p[23]=rd(46);p[24]=private_slot;p[25]=MAIL[7];p[26]=active_condition;p[27]=rd(49);
  record_count++;MAIL[2]=record_count;MAIL[3]=archive_used;
 }
 if(rc)wr(3,2);
 return rc;
}
static XUartPs uart;
static int uart_init(void){
 XUartPs_Config*c=XUartPs_LookupConfig(XPAR_XUARTPS_0_DEVICE_ID);
 if(!c || XUartPs_CfgInitialize(&uart,c,c->BaseAddress)!=0)return -1;
 if(XUartPs_SetBaudRate(&uart,115200)!=0)return -1;
 XUartPs_SetOperMode(&uart,XUARTPS_OPER_MODE_NORMAL);return 0;
}
static void terminal(uint32_t state){
 /* Also flush earlier successful archives on every failure exit. */
 if(ROI_CACHE_ENABLED && archive_used)Xil_DCacheFlushRange((UINTPTR)ARCHIVE,archive_used*4);
 if(ROI_CACHE_ENABLED && MAIL[10])Xil_DCacheFlushRange((UINTPTR)DENSE,MAIL[10]*4);
 __asm__ volatile("dmb sy" ::: "memory");MAIL[1]=state;__asm__ volatile("dmb sy" ::: "memory");
 xil_printf("ROI_CAMPAIGN_TERMINAL status=%08x records=%u archive_words=%u\r\n",state,record_count,archive_used);
 while(!XUartPs_IsTransmitEmpty(&uart)){}for(;;){};
}
/* Experimental arm selection and resident source-frame selection are outside
 * each request timer. Zero-detection/select costs inside PL remain timed. */
static int select_condition(unsigned case_no,unsigned condition){
 frame_input=FRAME_BANK+(case_no/17U)*FRAME_WORDS;active_condition=condition;
 if(launch_kind){wr(49,condition==2U);if((rd(49)&1U)!=(condition==2U))return -1;}
 else if(condition!=0U || rd(49)!=0U)return -1;
 return 0;
}
static uint32_t input_fnv(const uint32_t*p){
 uint32_t h=0x811c9dc5U;unsigned i;
 for(i=0;i<FRAME_WORDS;i++){h^=p[i];h*=16777619U;}return h;
}
int main(void){
 unsigned i,rep,order,condition,condition_count,required=0;
 Xil_DCacheFlush();Xil_DCacheDisable();
 Xil_SetTlbAttributes((UINTPTR)MAIL,DEVICE_MEMORY);
 Xil_SetTlbAttributes((UINTPTR)LAUNCH,DEVICE_MEMORY);
 if(ROI_CACHE_ENABLED)Xil_DCacheEnable();
 Xil_Out32(CFG+4,0);Xil_Out32(CFG+12,0);Xil_Out32(RSP+4,0xffffffff);Xil_Out32(RSP+12,0xffffffff);Xil_Out32(CFG,0);
 if(uart_init())return 1;
 for(i=0;i<32;i++)MAIL[i]=0;
 MAIL[0]=0x43303731U;MAIL[4]=COUNTS_PER_SECOND;MAIL[5]=ROI_CASES;MAIL[6]=REPEATS;MAIL[8]=ROI_CACHE_ENABLED;MAIL[21]=RECORD_WORDS;MAIL[25]=50000000U;
 operation=LAUNCH[1];launch_kind=LAUNCH[2];repeat_base=LAUNCH[3];initial_bank=LAUNCH[4];launch_ordinal=LAUNCH[5];
 if(LAUNCH[0]!=0x43303731U || operation>1U || launch_kind>1U || initial_bank>1U)terminal(0x80000101U);
 if(operation==0U){
  if(launch_ordinal>3U || launch_kind!=(launch_ordinal==1U || launch_ordinal==2U) ||
     repeat_base!=(launch_ordinal<2U?0U:3U) || initial_bank!=(launch_ordinal==3U))terminal(0x80000102U);
 }else if(!launch_kind || launch_ordinal!=99U || repeat_base!=0U || initial_bank!=0U)terminal(0x80000103U);
 condition_count=launch_kind?2U:1U;
 MAIL[7]=initial_bank;MAIL[11]=launch_ordinal;MAIL[12]=launch_kind;MAIL[13]=repeat_base;MAIL[14]=operation;MAIL[15]=initial_bank;
 MAIL[20]=launch_kind?6U:1U;MAIL[22]=operation?0U:ROI_CASES*REPEATS*condition_count;
 if(MAIL[22]!=LAUNCH[6])terminal(0x80000104U);
 if(rd(48)!=0x524f4931U)terminal(0x80000001U);
 for(i=0;i<4U;i++){
  MAIL[16+i]=input_fnv(FRAME_BANK+i*FRAME_WORDS);
  if(MAIL[16+i]!=ROI_INPUT_FNV[i])terminal(0x80000105U);
 }
 memset((void*)0x04000000U,0,DENSE_WORDS*4);memset((void*)0x04400000U,0,DENSE_WORDS*4);
 if(ROI_CACHE_ENABLED){Xil_DCacheFlushRange(0x04000000U,DENSE_WORDS*4);Xil_DCacheFlushRange(0x04400000U,DENSE_WORDS*4);}
 xil_printf("ROI_CAMPAIGN_START cases=%u repeats=%u cache=%u launch=%u kind=%u base=%u operation=%u\\r\\n",ROI_CASES,REPEATS,ROI_CACHE_ENABLED,launch_ordinal,launch_kind,repeat_base,operation);
 if(operation){
  /* Separate untimed dense-only launch. Host byte replay must PASS before ABBA. */
  for(i=0;i<4U;i++){
   if(select_condition(i*17U+1U,2U) || run(i*17U+1U,2U,99U,0U))terminal(0x80000106U);
   memcpy(DENSE+i*DENSE_WORDS,PRIVATE,DENSE_WORDS*4);
   MAIL[10]+=DENSE_WORDS;MAIL[26]|=1U<<i;MAIL[9]=++preparation_count;
  }
  terminal(1U);
 }
 if(repeat_base==0U){
  for(i=0;i<ROI_CASES;i++)required+=pop(ROI_MASKS[i])*15360U*condition_count;
  if(required>ARCHIVE_WORDS)terminal(0x80000004U);
 }
 for(i=0;i<ROI_CASES;i++)for(order=0;order<condition_count;order++){
  condition=launch_kind?1U+((i+order)&1U):0U;
  if(select_condition(i,condition) || run(i,2U,99U,0U))terminal(0x80000002U);
  MAIL[9]=++preparation_count;
 }
 for(rep=0;rep<REPEATS;rep++)for(i=0;i<ROI_CASES;i++)for(order=0;order<condition_count;order++){
  condition=launch_kind?1U+((repeat_base+rep+i+order)&1U):0U;
  if(select_condition(i,condition) || run(i,2U,repeat_base+rep,1U))terminal(0x80000003U);
 }
 terminal(1U);return 0;
}

