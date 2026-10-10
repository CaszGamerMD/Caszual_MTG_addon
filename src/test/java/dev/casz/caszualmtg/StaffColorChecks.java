package dev.casz.caszualmtg;

import java.util.List;

/** Standalone Java checks for arbitrary staff glow color validation. */
public final class StaffColorChecks {
 private static void ok(boolean condition,String label){
  if(!condition)throw new AssertionError(label);
 }
 public static void main(String[] args){
  ok(StaffColors.valid("#000000"),"black should be accepted");
  ok(StaffColors.valid("#ffffff"),"lower-case hex should be accepted");
  ok(StaffColors.valid("#A1b2C3"),"mixed-case hex should be accepted");
  for(String bad:List.of("","white","FFFFFF","#FFF","#GG0000","#1234567","123456","#12 456"))
   ok(!StaffColors.valid(bad),"invalid hex incorrectly accepted: "+bad);
  ok(StaffColors.normalize("#a1b2c3").equals("#A1B2C3"),"normalization");
  ok(StaffColors.rgb("#00fffe")==0x00FFFE,"full RGB decoding");
  ok(StaffColors.rgb("#000000")==0,"black valid");
  ok(StaffColors.rgb("#FFFFFF")==0xFFFFFF,"white valid");
  ok(StaffColors.teamName(0x00A1B2C3).equals("csrgb_A1B2C3"),"scoreboard name encoding");
  ok(StaffColors.teamName(0).equals("csrgb_000000"),"black scoreboard name");
  ok(StaffColors.teamName(0xFFFFFF).length()<=16,"Minecraft scoreboard naming limit");
  System.out.println("CASZUAL_STAFF_RGB_PASS: arbitrary #RRGGBB parsing, safety and scoreboard naming");
 }
 private StaffColorChecks(){}
}
