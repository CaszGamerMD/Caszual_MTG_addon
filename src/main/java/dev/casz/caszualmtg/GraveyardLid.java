package dev.casz.caszualmtg;

/** Persistent display-lid state for custom graveyards, independently of GUI viewers. */
public interface GraveyardLid {
 boolean caszual$isLidPinned();
 void caszual$setLidPinned(boolean open);
}
