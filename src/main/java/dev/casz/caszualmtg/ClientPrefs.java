package dev.casz.caszualmtg;

import net.fabricmc.loader.api.FabricLoader;
import java.io.*;
import java.nio.file.*;
import java.util.Properties;

/** Small persistent client preferences shared by every Caszual MTG browser UI. */
public final class ClientPrefs {
 private static final Path FILE=FabricLoader.getInstance().getConfigDir().resolve("caszual_mtg-client.properties");
 private static boolean grid=loadGrid();
 private ClientPrefs(){}

 public static boolean grid(){return grid;}

 public static void setGrid(boolean value){
  grid=value;
  Properties p=new Properties();
  p.setProperty("cardView",value?"grid":"list");
  try{
   Files.createDirectories(FILE.getParent());
   try(Writer out=Files.newBufferedWriter(FILE)){p.store(out,"Caszual MTG client preferences");}
  }catch(IOException ignored){}
 }

 private static boolean loadGrid(){
  Properties p=new Properties();
  if(Files.isRegularFile(FILE))try(Reader in=Files.newBufferedReader(FILE)){p.load(in);}catch(IOException ignored){}
  return "grid".equalsIgnoreCase(p.getProperty("cardView","list"));
 }
}
