package dev.casz.caszualmtg;

import net.minecraft.world.Container;
import java.lang.reflect.Method;

/** Safeguards owner-only card data against generic inventory inspectors (Jade etc). */
public final class HandPrivacyCheck {
 public static void main(String[] args) {
  if(Container.class.isAssignableFrom(HandBlockEntity.class))
   throw new AssertionError("Card Hand must not advertise itself as a generic Container");
  for(Method m:HandBlockEntity.class.getMethods()){
   if(m.getDeclaringClass()!=HandBlockEntity.class)continue;
   if(m.getName().equals("getItem")||m.getName().equals("getContainerSize")
      ||m.getName().equals("removeItem")||m.getName().equals("clearContent"))
    throw new AssertionError("Card Hand inventory exposed by public method: "+m.getName());
  }
  System.out.println("CARD_HAND_PRIVACY_PASS: card inventory is not exposed to generic container inspectors.");
 }
 private HandPrivacyCheck(){}
}
