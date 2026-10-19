package dev.casz.caszualmtg;

import java.util.*;

/** Validated, per-player tabletop bindings stored on the Card Hand. */
public final class HandHotkeys {
 public static final List<String> ACTIONS=List.of("draw","untap_all","pass_turn","shuffle","mill");
 private HandHotkeys(){}
 public static boolean validAction(String action){return ACTIONS.contains(action);}
 public static boolean validKey(int key){
  // GLFW printable keys and function keys. Never allow modifier-only keys.
  return key>=32&&key<=348&&key!=256&&key!=257&&key!=258&&key!=259
      &&key!=260&&key!=261&&key!=262&&key!=263&&key!=264&&key!=265
      &&key!=266&&key!=267&&key!=268&&key!=269&&key!=280&&key!=281
      &&key!=282&&key!=283&&key!=284&&key!=340&&key!=341&&key!=342
      &&key!=343&&key!=344&&key!=345&&key!=346&&key!=347&&key!=348;
 }
 public static Map<String,Integer> sanitize(Map<String,Integer> raw){
  Map<String,Integer> safe=new LinkedHashMap<>();
  if(raw!=null)for(String action:ACTIONS){
   Integer key=raw.get(action);
   if(key!=null&&validKey(key))safe.put(action,key);
  }
  return Map.copyOf(safe);
 }
}
