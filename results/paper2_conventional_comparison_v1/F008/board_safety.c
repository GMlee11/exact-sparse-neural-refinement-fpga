/* Separate physical fault/reuse qualification; no performance measurements.
 * Reuse precisely the qualified host/DMA/cache primitives without changing the
 * frozen performance source. The final mailbox has a distinct safety marker. */
#define main roi_campaign_main
#include "board_campaign.c"
#undef main
#define SAFETY_MARKER 0x53414631U
#define SAFETY_ROW 0x53544654U
static uint32_t baseline_checksum;
static unsigned distinct_private_output;
static const unsigned seed_case=2; /* Frozen clustered_rectangles_10, six tiles. */
static uint32_t public_checksum(void){
 private_target=(uint32_t*)(0x04000000U+(MAIL[7]&1U)*0x00400000U);
 return checksum(ROI_MASKS[seed_case]);
}
static unsigned public_equal_seed(void){
 unsigned y,c,k,count=0;
 private_target=(uint32_t*)(0x04000000U+(MAIL[7]&1U)*0x00400000U);
 for(y=0;y<720;y++)for(c=0;c<10;c++)if(bit(ROI_MASKS[seed_case],y/120,c))for(k=0;k<128;k++)
  if(PRIVATE[y*1280+c*128+k]!=ARCHIVE[count++])return 0;
 return count==pop(ROI_MASKS[seed_case])*15360;
}
static void safety_record(unsigned id,unsigned okay,uint32_t old_token,unsigned expected,unsigned private_before,unsigned regions_before){
 uint32_t s=status(),sum=public_checksum();unsigned offset=save_bytes(ROI_MASKS[seed_case]);
 volatile uint32_t*p=MAIL+32+record_count*RECORD_WORDS;unsigned k;
 for(k=0;k<RECORD_WORDS;k++)p[k]=0;
 p[0]=SAFETY_ROW;p[1]=id;p[2]=okay;p[3]=s;p[4]=old_token;p[5]=MAIL[7];p[6]=baseline_checksum;p[7]=sum;
 p[8]=private_before;p[9]=regions_before;p[10]=rd(5);p[11]=expected;p[12]=frame_id;p[13]=rd(19);p[14]=public_equal_seed();p[15]=distinct_private_output;
 p[20]=offset;p[21]=pop(ROI_MASKS[seed_case])*15360;record_count++;MAIL[2]=record_count;MAIL[3]=archive_used;
 if(!okay || offset==0xffffffffU || !p[14] || sum!=baseline_checksum)terminal(0x80000005);
}
static int begin_fault(unsigned deadline){
 uint64_t mask=(1ULL<<24)|(1ULL<<59);wr(3,4);if(dma_init())return -1;
 private_slot=(MAIL[7]&1U)^1U;private_target=(uint32_t*)(0x04000000U+private_slot*0x00400000U);distinct_private_output=0;
 wr(0,(uint32_t)mask);wr(1,(uint32_t)(mask>>32));wr(16,++frame_id);wr(17,0);wr(18,50000000U);wr(3,deadline?9:1);
 return 0;
}
static int first_private_region(void){
 Region q=expanded(256,120,64,60,1ULL<<24);unsigned nin=pack(&q),y,k;
 wr(2,nin);wr(39,q.x|(q.y<<16));wr(40,q.w|(q.h<<16));wr(41,1U<<24);wr(42,0);wr(43,0);wr(3,16);dma_start(nin,15360);
 if(wait_region(0))return -1;
 Xil_DCacheInvalidateRange((UINTPTR)RX,15360*4);if(scatter(&q)!=15360)return -1;
 uint32_t*published=(uint32_t*)(0x04000000U+(MAIL[7]&1U)*0x00400000U);
 for(y=240;y<360;y++)for(k=512;k<640;k++)if(PRIVATE[y*1280+k]!=published[y*1280+k])distinct_private_output=1;
 return rd(44)==15360 && rd(46)==1 && !(status()&4) && distinct_private_output?0:-1;
}
static void invert_input(void){unsigned k;for(k=0;k<360*640;k++)INPUT[k]^=0x00ffffffU;}
static int wait_terminal(void){
 uint64_t start=now();while(!(status()&2))if(now()-start>TIMEOUT_TICKS)return -1;return 0;
}
int main(void){
 unsigned i,y,x,c;Xil_DCacheFlush();Xil_DCacheDisable();Xil_SetTlbAttributes((UINTPTR)MAIL,DEVICE_MEMORY);Xil_DCacheEnable();
 Xil_Out32(CFG+4,0);Xil_Out32(CFG+12,0);Xil_Out32(RSP+4,0xffffffff);Xil_Out32(RSP+12,0xffffffff);Xil_Out32(CFG,0);
 if(uart_init())return 1;
 for(i=0;i<32;i++)MAIL[i]=0;MAIL[0]=0x524f4931;MAIL[4]=COUNTS_PER_SECOND;MAIL[5]=ROI_CASES;MAIL[6]=1;MAIL[8]=1;MAIL[9]=SAFETY_MARKER;
 xil_printf("ROI_SAFETY_START tests=11 cache=1\r\n");
 if(rd(48)!=0x524f4931)terminal(0x80000001);
 for(y=0;y<360;y++)for(x=0;x<640;x++){uint32_t v=0;for(c=0;c<3;c++)v|=((17*y+29*x+43*c+51-128)&255)<<(c*8);INPUT[y*640+x]=v;}
 if(run(seed_case,1,99,0))terminal(0x80000006);
 baseline_checksum=public_checksum();safety_record(0,1,0,1,rd(44),rd(46));
 for(i=0;i<5;i++){
  uint32_t token=MAIL[7],prior_committed=rd(19);unsigned expected=i==0?3:i==1?4:5,private_before=0,regions_before=0;
  invert_input();
  if(begin_fault(i==1))terminal(0x80000007);
  if(i==0 || i==1 || i==3){if(first_private_region())terminal(0x80000008);private_before=rd(44);regions_before=rd(46);}
  if(i==0)wr(3,2); /* Cancel after a complete private, nonfinal region. */
  else if(i==1){wr(18,0xffffffffU);wr(3,0);} /* Cannot extend/disable accepted deadline. */
  else if(i==2){wr(39,256|(120U<<16));wr(40,64|(60U<<16));wr(41,1U<<24);wr(42,0);wr(43,0);wr(3,16);} /* Missing halo. */
  else if(i==3){wr(3,16);} /* Same region descriptor again: duplicate ownership. */
  else {wr(16,0xeeeeeeeeU);wr(3,1);} /* Malformed active restart. */
  unsigned okay=wait_terminal()==0;uint32_t s=status();
  okay=okay && !(s&1) && !(s&4) && ((s>>5)&7)==expected && MAIL[7]==token && rd(19)==prior_committed;
  if(i==1)okay=okay && rd(5)>=50000000U && rd(5)<=50000002U;
  safety_record(1+i*2,okay,token,expected,private_before,regions_before);
  invert_input();
  /* No PL reset: PREPARE in run() must clear fault state for real-output reuse. */
  if(run(seed_case,1,99,0))terminal(0x80000009);
  okay=(status()&4) && !(status()&16) && rd(19)==frame_id && MAIL[7]!=token;
  safety_record(2+i*2,okay,token,1,rd(44),rd(46));
 }
 terminal(1);return 0;
}
