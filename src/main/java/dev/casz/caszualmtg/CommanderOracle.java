package dev.casz.caszualmtg;
/** Remove balanced reminder text only; leave all actual ability clauses intact. */
public final class CommanderOracle {
 private CommanderOracle(){}
 public static String rules(String text){
  if(text==null)return "";
  StringBuilder out=new StringBuilder();int depth=0;
  for(char c:text.toCharArray()){
   if(c=='('){depth++;continue;}
   if(c==')'){if(depth==0)return text;depth--;continue;}
   if(depth==0)out.append(c);
  }
  return depth==0?out.toString().strip():text;
 }
}
