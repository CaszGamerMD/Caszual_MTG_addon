"""Public Deck Control reveals and native-compatible custom MTG devices."""
import unittest,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
J=R/"src/main/java/dev/casz/caszualmtg"
D=R/"src/main/resources"
def source(p):return (J/p).read_text()

class PublicDeckReveals(unittest.TestCase):
 def test_only_real_reveals_are_sent_to_all_connected_players(self):
  logic=source("TabletopLogic.java")
  wire=source("TabletopWire.java")
  screen=source("TabletopScreen.java")
  self.assertIn('List<TabletopWire.PublicReveal> publicReveals',logic)
  self.assertIn('ScrySession publicSession=REVEALS.get(owner)',logic)
  self.assertIn('if(publicSession==null)continue',logic)
  self.assertIn('HandBlockEntity ownerHand=linkedHand(player,table,owner)',logic)
  self.assertIn('!publicSession.control().equals(control.getBlockPos())',logic)
  self.assertIn('new TabletopWire.PublicReveal(table.getBlockPos(),table.seatName(),publicSession.cards())',logic)
  self.assertIn('List.copyOf(publicReveals)',logic)
  self.assertIn('record PublicReveal(BlockPos seat,String owner,List<ItemStack> cards)',wire)
  self.assertIn('b.writeVarInt(p.publicReveals.size())',wire)
  self.assertIn('Too many publicly revealed cards',wire)
  self.assertIn('publicReveals.add(new PublicReveal',wire)
  self.assertIn('for(var deck:data.publicReveals())if(deck.seat().equals(view))return deck',screen)
  self.assertIn('DECK REVEAL · ',screen)
  self.assertIn('drawArt(g,revealedDeck.cards().get(i)',screen)
  self.assertIn('revealStripAt(mx,my)',screen)
  self.assertIn('if(revealStripAt(x,y)>=0)return true',screen)

 def test_native_deck_control_and_graveyard_are_preserved(self):
  dc=source("CustomDeckControl.java")
  gy=source("CustomGraveyard.java")
  reg=source("CaszualMtg.java")
  safe=source("MtgBlockEntitySafety.java")
  self.assertIn('extends DeckControlBlock',dc)
  self.assertIn('extends GraveyardBlock',gy)
  self.assertNotIn('new DeckControlBlockEntity',dc)
  self.assertNotIn('new GraveyardBlockEntity',gy)
  self.assertIn('super.useItemOn(',dc)
  self.assertIn('super.useItemOn(',gy)
  self.assertIn('CustomGameDeviceMaterial.apply(',dc)
  self.assertIn('CustomGameDeviceMaterial.apply(',gy)
  self.assertIn('CUSTOM_DECK_CONTROL=customDeckControl()',reg)
  self.assertIn('CUSTOM_GRAVEYARD=customGraveyard()',reg)
  self.assertIn('ensure(ModBlockEntities.DECK_CONTROL, CaszualMtg.CUSTOM_DECK_CONTROL',safe)
  self.assertIn('ensure(ModBlockEntities.GRAVEYARD, CaszualMtg.CUSTOM_GRAVEYARD',safe)
  self.assertIn('e.accept(CUSTOM_DECK_CONTROL);e.accept(CUSTOM_GRAVEYARD)',reg)
  self.assertIn('return new CustomDeckControlEntity(pos,state)',dc)
  self.assertIn('return new CustomGraveyardEntity(pos,state)',gy)
  self.assertIn('extends DeckControlBlockEntity',source('CustomDeckControlEntity.java'))
  self.assertIn('extends GraveyardBlockEntity',source('CustomGraveyardEntity.java'))
  self.assertIn('ClientboundBlockEntityDataPacket.create(this)',source('CustomDeckControlEntity.java'))
  self.assertIn('ClientboundBlockEntityDataPacket.create(this)',source('CustomGraveyardEntity.java'))
  self.assertIn('out.putString("CaszualMaterial"',source('CustomGraveyardEntity.java'))

 def test_materials_and_all_models_have_stable_assets(self):
  mix=json.loads((D/"caszual_mtg.mixins.json").read_text())
  self.assertIn('DeckControlMaterialMixin',mix['mixins'])
  self.assertIn('GraveyardMaterialMixin',mix['mixins'])
  for name in ['DeckControlMaterialMixin.java','GraveyardMaterialMixin.java']:
   s=source("mixin/"+name)
   self.assertIn('implements BoxMaterial',s)
   self.assertIn('input.getStringOr("CaszualMaterial"',s)
   self.assertIn('output.putString("CaszualMaterial"',s)
   self.assertIn('getRenderData()',s)
  models=source("CustomBoxModels.java")
  self.assertIn('new DeviceWorldModel(model)',models)
  self.assertIn('new DeviceItemModel(model)',models)
  self.assertIn('remap(q,skin,CHAIR_SOURCE)',models)
  for name in ['custom_deck_control','custom_graveyard']:
   for prefix in ['assets/caszual_mtg/blockstates/','assets/caszual_mtg/items/','assets/caszual_mtg/models/item/','data/caszual_mtg/recipe/','data/caszual_mtg/loot_table/blocks/']:
    file=D/(prefix+name+'.json')
    assert file.is_file(),file
    json.loads(file.read_text())
  dc=json.loads((D/"assets/caszual_mtg/blockstates/custom_deck_control.json").read_text())
  self.assertEqual(36,len(dc["multipart"]))
  gy=json.loads((D/"assets/caszual_mtg/blockstates/custom_graveyard.json").read_text())
  self.assertEqual(8,len(gy["variants"]))
  for name in ['custom_deck_control','custom_graveyard_open','custom_graveyard_closed']:
   json.loads((D/f"assets/caszual_mtg/models/block/{name}.json").read_text())

if __name__=="__main__":unittest.main()
