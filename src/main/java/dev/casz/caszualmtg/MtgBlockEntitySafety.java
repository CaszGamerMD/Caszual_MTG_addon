package dev.casz.caszualmtg;

import com.spider.mtgcard.registry.ModBlockEntities;
import com.spider.mtgcard.registry.ModBlocks;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.BlockEntityType;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * MTGCard 1.7.0 block-entity compatibility guard.
 *
 * In some mod-initialization orders MTGCard's type builder can capture
 * an incomplete set of registered blocks. A deckbox or Card Store will then
 * throw BlockEntity.validateBlockState when the client first reads it.
 *
 * Only add blocks owned by MTGCard (plus this addon's deckbox subclass).
 * Never replace an existing BE type or block instance: existing world data
 * and the native MTGCard deckbox/card-store implementations stay intact.
 */
public final class MtgBlockEntitySafety {
    private static final Logger LOGGER = LoggerFactory.getLogger("caszual_mtg");
    private static boolean checked;

    private MtgBlockEntitySafety() {}

    /**
     * Called only after Fabric has initialized the mods. Returns false (without
     * failing startup) if MTGCard's initializer has not run yet.
     */
    public static synchronized boolean verifyIfReady() {
        if (checked) return true;

        // An addon entrypoint can run before MTGCard finishes its registration.
        // Never call MTGCard's init() here and never abort client boot over timing.
        if (ModBlockEntities.DECKBOX == null || ModBlockEntities.CARD_STORE == null
                || ModBlockEntities.DECK_CONTROL == null || ModBlockEntities.GRAVEYARD == null
                || ModBlockEntities.DISPLAY_BLOCK == null || ModBlockEntities.CARD_DB == null) {
            return false;
        }

        int repaired = 0;
        for (Block block : ModBlocks.getDeckboxBlocks()) {
            repaired += ensure(ModBlockEntities.DECKBOX, block, "MTGCard deckbox");
        }
        repaired += ensure(ModBlockEntities.DECKBOX, CaszualMtg.CUSTOM_BOX, "Caszual custom deckbox");
        repaired += ensure(ModBlockEntities.CARD_STORE, ModBlocks.CARD_STORE, "MTGCard Card Store");

        repaired += ensure(ModBlockEntities.DECK_CONTROL, ModBlocks.DECK_CONTROL_STONE, "deck control");
        repaired += ensure(ModBlockEntities.DECK_CONTROL, ModBlocks.DECK_CONTROL_POLISHED_GRANITE, "deck control");
        repaired += ensure(ModBlockEntities.DECK_CONTROL, ModBlocks.DECK_CONTROL_POLISHED_DIORITE, "deck control");
        repaired += ensure(ModBlockEntities.DECK_CONTROL, ModBlocks.DECK_CONTROL_POLISHED_ANDESITE, "deck control");
        repaired += ensure(ModBlockEntities.DECK_CONTROL, ModBlocks.DECK_CONTROL_POLISHED_TUFF, "deck control");
        repaired += ensure(ModBlockEntities.DECK_CONTROL, ModBlocks.DECK_CONTROL_POLISHED_SULFUR, "deck control");
        repaired += ensure(ModBlockEntities.DECK_CONTROL, ModBlocks.DECK_CONTROL_POLISHED_CINNABAR, "deck control");
        repaired += ensure(ModBlockEntities.DECK_CONTROL, ModBlocks.DECK_CONTROL_POLISHED_DEEPSLATE, "deck control");
        repaired += ensure(ModBlockEntities.DECK_CONTROL, ModBlocks.DECK_CONTROL_POLISHED_BLACKSTONE, "deck control");
        repaired += ensure(ModBlockEntities.DECK_CONTROL, ModBlocks.DECK_CONTROL_PRISMARINE, "deck control");
        repaired += ensure(ModBlockEntities.DECK_CONTROL, ModBlocks.DECK_CONTROL_CUT_SANDSTONE, "deck control");
        repaired += ensure(ModBlockEntities.DECK_CONTROL, ModBlocks.DECK_CONTROL_CUT_RED_SANDSTONE, "deck control");

        repaired += ensure(ModBlockEntities.GRAVEYARD, ModBlocks.GRAVEYARD, "graveyard");
        repaired += ensure(ModBlockEntities.DISPLAY_BLOCK, ModBlocks.DISPLAY_BLOCK, "display block");
        repaired += ensure(ModBlockEntities.CARD_DB, ModBlocks.CARD_DB, "Card Database");

        // Don't claim initialization was checked until every native state is valid.
        checked = true;
        if (repaired > 0) {
            LOGGER.warn("Repaired {} missing MTGCard block-entity/block associations. "
                    + "Original block entities and their saved contents remain unchanged.", repaired);
        } else {
            LOGGER.info("Verified MTGCard block-entity associations (including Card Store and deckboxes).");
        }
        return true;
    }

    /** Deferred to the first client-start/server-start lifecycle checkpoint. */
    public static void verifyAtLifecycle(String phase) {
        try {
            if (!verifyIfReady()) {
                LOGGER.warn("MTGCard block-entity registrations are still unavailable at {}. "
                        + "Check the installed MTGCard version and logs; Caszual MTG won't abort startup.", phase);
            }
        } catch (RuntimeException error) {
            LOGGER.error("Could not validate MTGCard block-entity registrations at {}. "
                    + "Deferring the error instead of crashing Minecraft during startup.", phase, error);
        }
    }

    /** Make a BE type recognize the already-registered block, without replacing either. */
    private static int ensure(BlockEntityType<?> type, Block block, String description) {
        if (block == null) {
            throw new IllegalStateException("Missing MTGCard block for " + description);
        }
        if (type.isValid(block.defaultBlockState())) return 0;
        type.addValidBlock(block);
        if (!type.isValid(block.defaultBlockState())) {
            throw new IllegalStateException("Failed to repair MTGCard block entity for "
                    + description + ": " + block);
        }
        LOGGER.warn("Added missing valid block to MTGCard block-entity type ({}): {}", description, block);
        return 1;
    }
}
