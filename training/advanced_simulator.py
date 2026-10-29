"""Reusable group combat, station/history actions, and blink/rebound operations."""
from dataclasses import replace,asdict
from itertools import combinations
import sys
import json

def model(sim):return sys.modules[type(sim).__module__]
def root(card):return card.physical_id or card.id

class AdvancedRules:
 def role_targets(self,event):
  g=self.event_game('main');controller=event['controller']
  return tuple(p for p in self.players[controller].battlefield
   if p.card.id!=event['source'] and p.card.id in g.battlefield and g.creature(g.battlefield[p.card.id])
   and not g.protected(g.battlefield[p.card.id],event.get('sourceColors',())))
 def resolve_role(self,event):
  s=model(self);target=next((p for p in self.role_targets(event) if p.card.id==event['target']),None)
  if target is None:
   self.log('role_illegal_target','The Role trigger has no remaining legal target.',source=event['source'],target=event['target'])
   return
  self.token_sequence+=1
  d=s.EventDefinition('Virtuous Role',frozenset({'Enchantment'}),frozenset({'Aura','Role'}),False,0,0,frozenset(),
   attachment=('aura',None,frozenset(),0,0),attachment_scale=(1,1,('Enchantment',)),role='Virtuous')
  token=s.Card('token-'+str(self.token_sequence),d.name,'aura',event_definition=d,is_token=True,printed_types=('Enchantment',))
  pending=self.enter_creature(token,self.players[event['controller']],attached_to=target.card.id)
  self.log('role_created','A Virtuous Role enters attached to another creature.',actor=event['controller'],source=event['source'],target=target.card.id,token=token.id)
  self.resolve_entry_triggers(pending,token)
 def choose_optional_draw(self,event):
  s=model(self);seat=event['controller']
  choices=(s.Candidate('draw','optional_draw',features=s.features(draw=1,power=0 if self.players[seat].library else -1000),label='Draw a card'),
           s.Candidate('decline','decline_draw',features=s.features(),label='Decline drawing'))
  observation=s.Observation(seat,self.turn,self.phase,tuple(self.players[seat].hand),json.dumps(self.state(),sort_keys=True),choices)
  choice=self.policies[seat].choose(observation)
  if choice not in choices:raise ValueError('Illegal optional draw choice')
  self.log('optional_draw_choice',choice.label,actor=seat,source=event['source'],accepted=choice.kind=='optional_draw')
  return choice.kind=='optional_draw'
 def special_choices(self,seat):
  s=model(self);result=[];g=self.event_game('main')
  for p in self.players[seat].battlefield:
   d=p.card.event_definition
   if not d:continue
   if d.history_activation and not p.tapped and (not g.creature(g.battlefield[p.card.id]) or not p.fresh or g.has(g.battlefield[p.card.id],'haste')):
    count=self.history_count(seat,d.history_activation[0])
    result.append(s.Candidate(p.card.id+':history','history_tokens',p.card.id,features=s.features(power=count if count else -100),label='Activate '+p.card.name))
   if d.station and seat==self.active and self.phase in ('main','second_main') and not self.stack.items:
    for helper in self.players[seat].battlefield:
     state=g.battlefield.get(helper.card.id)
     if helper is not p and state and not helper.tapped and g.creature(state):
      power=max(0,g.stats(state)[0]);remaining=max(0,d.station[-1][0]-p.charge_counters)
      result.append(s.Candidate(p.card.id+':station:'+helper.card.id,'station',p.card.id,
       features=s.features(power=.5+min(power,remaining) if remaining and power else -100),label='Station '+p.card.name,tap_ids=(helper.card.id,)))
  return result
 def activate_transport(self,seat,kind,identifier,helpers):
  if self.stack.priority!=seat or kind not in ('crew','saddle'):raise ValueError('Illegal transport activation')
  if kind=='saddle' and (seat!=self.active or self.phase not in ('main','second_main') or self.stack.items):raise ValueError('Saddle only as a sorcery')
  game=self.event_game('main' if self.phase in ('main','second_main') else 'combat')
  source=game.battlefield.get(identifier)
  if source is None:raise ValueError('Missing transport source')
  old_animated,old_saddled=source.animated,source.saddled
  getattr(game,kind)(identifier,list(helpers),seat)
  source.animated,source.saddled=old_animated,old_saddled
  self.sync_events(game)
  card=next(p.card for p in self.players[seat].battlefield if p.card.id==identifier)
  event=dict(operation='transport',effect=kind,kind=kind,controller=seat,source=identifier,name=card.name)
  self.stack.push(seat,(event,card),card.name+' '+kind);self.stack.priority=seat
  self.log(kind,'Transport activation costs are paid.',actor=seat,target=identifier,tapped=list(helpers))
  if not self.manual_priority and not self._resolving_stack:self.drain_priority()
 def history_count(self,seat,subtypes):
  return sum(e['turn']==self.turn and e['controller']==seat and bool(set(subtypes)&set(e['subtypes'])) for e in self.entry_history)
 def activate_history(self,seat,identifier):
  if self.stack.priority!=seat:raise ValueError('Player lacks priority')
  p=next((p for p in self.players[seat].battlefield if p.card.id==identifier),None);g=self.event_game('main')
  if not p or not p.card.event_definition or not p.card.event_definition.history_activation or p.tapped:raise ValueError('Illegal history activation')
  state=g.battlefield[identifier]
  if g.creature(state) and p.fresh and not g.has(state,'haste'):raise ValueError('Summoning sickness prevents tap activation')
  p.tapped=True;watch,spec=p.card.event_definition.history_activation
  event=dict(operation='history_tokens',controller=seat,name=p.card.name,source=identifier,watch=list(watch),tokenSpec=dict(asdict(spec),keywords=sorted(spec.keywords)))
  frame=self.stack.push(seat,(event,p.card),p.card.name+' activated ability');self.stack.priority=seat
  self.log('history_activate','Entry-history token ability is activated.',actor=seat,stackId=frame.id)
  if not self.manual_priority and not self._resolving_stack:self.drain_priority()
 def activate_station(self,seat,identifier,helper_id):
  if seat!=self.active or self.phase not in ('main','second_main') or self.stack.items or self.stack.priority!=seat:raise ValueError('Station only as a sorcery')
  p=next((p for p in self.players[seat].battlefield if p.card.id==identifier),None)
  helper=next((p for p in self.players[seat].battlefield if p.card.id==helper_id),None);g=self.event_game('main')
  if not p or not p.card.event_definition or not p.card.event_definition.station or not helper or helper is p or helper.tapped or not g.creature(g.battlefield[helper_id]):raise ValueError('Illegal station helper')
  power=g.stats(g.battlefield[helper_id])[0];helper.tapped=True
  event=dict(operation='station',controller=seat,name=p.card.name,source=identifier,helper=helper_id,lastPower=power)
  frame=self.stack.push(seat,(event,p.card),p.card.name+' station ability');self.stack.priority=seat
  self.log('station_activate','A creature operates a station.',actor=seat,source=identifier,helper=helper_id,stackId=frame.id)
  if not self.manual_priority:self.drain_priority()
 def blink_choices(self,seat,card,kind='respond'):
  s=model(self);result=[]
  for owner,p in self.creature_targets(seat,card):
   if owner!=seat:continue
   threatened=any(f.controller!=seat and f.payload[0].get('target')==p.card.id for f in self.stack.items)
   value=3 if threatened else .6 if p.card.event_definition and p.card.event_definition.triggers else .2 if p.tapped else -1
   if p.card.is_token:value=-100
   result.append(s.Candidate(card.id+':blink:'+p.card.id,kind,card.id,features=s.features(power=value,cost=0 if kind=='rebound_cast' else len(self.payment(card,seat=seat).get('sources',[]))),label='Blink '+p.card.name,target_permanent=p.card.id))
  return result
 def blink_permanent(self,owner,item):
  s=model(self);old=item.card;physical=root(old);destination=self.card_owners.get(physical,owner)
  self.send_to_destination(self.players[owner],item)
  if old.is_token:
   self.log('blink_token','An exiled token cannot return.',actor=owner,oldObject=old.id);return
  p=self.players[destination]
  if old in p.graveyard:p.graveyard.remove(old)
  if p.command_zone and root(p.command_zone)==physical:p.command_zone=None
  self.object_sequence+=1
  returned=replace(old,id=physical+'@'+str(self.object_sequence),physical_id=physical)
  pending=self.enter_creature(returned,p)
  self.log('blink','A creature returns as a new object.',actor=destination,oldObject=old.id,newObject=returned.id,physicalCard=physical)
  self.resolve_entry_triggers(pending,returned)
 def can_block(self,attacker,blocker):
  g=self.event_game('combat');a=g.battlefield.get(attacker.card.id);b=g.battlefield.get(blocker.card.id)
  return bool(a and b and g.creature(a) and g.creature(b) and not blocker.tapped
   and (not g.has(a,'flying') or g.has(b,'flying') or g.has(b,'reach'))
   and not g.protected(a,b.definition.colors))
 def attackable(self,seat):
  g=self.event_game('combat')
  return [p for p in self.players[seat].battlefield if p.card.id in g.battlefield and g.creature(g.battlefield[p.card.id]) and not p.tapped
   and not g.has(g.battlefield[p.card.id],'defender') and (not p.fresh or g.has(g.battlefield[p.card.id],'haste'))]
 def group_attack_choices(self,seat):
  s=model(self);available=self.attackable(seat);ids=[p.card.id for p in available]
  required={p.card.id for p in available if p.card.name=='Zurgo Helmsmasher'}
  groups={tuple(ids)} if ids else set()
  groups.update((i,) for i in ids)
  if len(ids)<=6:
   groups.update(group for n in range(2,len(ids)) for group in combinations(ids,n))
  result=[]
  for group in sorted(groups):
   if not group or not required<=set(group):continue
   power=sum(max(0,self.effective_card(p).power) for p in available if p.card.id in group)
   result.append(s.Candidate('attack:'+','.join(group),'attack_group',group[0],features=s.features(power=power/10,damage=power,lethal=int(power>=self.players[1-seat].life)),label='Attack with '+str(len(group))+' creatures',attack_ids=group))
  if not required:result.append(s.Candidate('pass','pass',features=s.features(**{'pass':1}),label='Pass'))
  return tuple(result)
 def declare_attackers(self,identifiers):
  if self.phase!='attack' or self.stack.items or self.stack.priority!=self.active:raise ValueError('Illegal attack timing')
  ids=list(identifiers);eligible={p.card.id:p for p in self.attackable(self.active)}
  if len(set(ids))!=len(ids) or any(i not in eligible for i in ids):raise ValueError('Illegal attack group')
  required={p.card.id for p in eligible.values() if p.card.name=='Zurgo Helmsmasher'}
  if not required<=set(ids):raise ValueError('Required attacker omitted')
  if not ids:self.phase='second_main';return
  self.group_combat=dict(attackers=list(ids),declared=list(ids),blocks={},blocked=set(),early=None)
  g=self.event_game('combat');events=[]
  for identifier in ids:
   g.attack(identifier,1-self.active,defer=True)
   p=g.battlefield[identifier]
   for operation,minimum,_,spec in p.definition.attack_effects:
    if (operation=='attack_tokens' or operation=='group_tokens' and len(ids)>=minimum+1
        or operation=='saddled_tokens' and p.saddled):
     events.append(dict(operation='create_tokens',effect='attack token creation',source=identifier,controller=p.controller,name=p.definition.name,tokenSpec=dict(asdict(spec),keywords=sorted(spec.keywords))))
   for equipment in g.battlefield.values():
    if equipment.attached_to==identifier:
     for spec in equipment.definition.equipment_attacks:
      events.append(dict(operation='create_tokens',effect='equipped attack token creation',source=equipment.id,controller=equipment.controller,name=equipment.definition.name,tokenSpec=dict(asdict(spec),keywords=sorted(spec.keywords))))
  self.sync_events(g)
  events=[e for e in g.events if e['kind']=='trigger' and e.get('operation')]+events
  self.pending=ids[0];self.phase='block'
  self.log('attack_group','Creatures attack simultaneously.',attackers=ids)
  self.resolve_entry_triggers(events,eligible[ids[0]].card)
  if not self.manual_priority and not self.finished:self.drain_priority(empty_window=True)
 def group_block_choices(self,seat):
  s=model(self);combat=self.group_combat;attackers=[p for p in self.players[self.active].battlefield if p.card.id in combat['attackers'] and self.effective_card(p)]
  blockers=[p for p in self.players[seat].battlefield if self.effective_card(p) and not p.tapped]
  maps=[{}];greedy={};used=set();g=self.event_game('combat')
  for a in sorted(attackers,key=lambda p:self.effective_card(p).power,reverse=True):
   legal=[b for b in blockers if b.card.id not in used and self.can_block(a,b)]
   minimum=2 if g.has(g.battlefield[a.card.id],'menace') else 1
   if len(legal)>=minimum:
    chosen=sorted(legal,key=lambda p:self.effective_card(p).power+self.effective_card(p).toughness,reverse=True)[:minimum]
    greedy[a.card.id]=tuple(b.card.id for b in chosen);used.update(greedy[a.card.id])
   for group in combinations(legal,minimum):maps.append({a.card.id:tuple(b.card.id for b in group)})
  if greedy:maps.append(greedy)
  result=[]
  for index,mapping in enumerate(maps):
   damage=0;trade=0
   for a in attackers:
    ac=self.effective_card(a);chosen=[b for b in blockers if b.card.id in mapping.get(a.card.id,())]
    if not chosen:damage+=max(0,ac.power)
    else:
     bc=self.effective_card(chosen[0]);trade+=ac.power if bc.power>=ac.toughness else 0
     if 'trample' in ac.traits:damage+=max(0,ac.power-bc.toughness)
   result.append(s.Candidate('blocks:'+str(index),'group_blocks',features=s.features(damage=-damage,lethal=-int(damage>=self.players[seat].life),power=trade/10),label='Declare blockers',blocks=tuple((a,tuple(bs)) for a,bs in mapping.items())))
  return tuple(result)
 def declare_blockers(self,mapping):
  if not self.group_combat or self.phase!='block' or self.stack.items:raise ValueError('Illegal block timing')
  combat=self.group_combat;used=set();defender=1-self.active
  attackers={p.card.id:p for p in self.players[self.active].battlefield if p.card.id in combat['attackers'] and self.effective_card(p)}
  blockers={p.card.id:p for p in self.players[defender].battlefield};g=self.event_game('combat')
  for identifier,chosen in mapping.items():
   if identifier not in attackers:raise ValueError('Missing attacking creature')
   if len(chosen)==1 and g.has(g.battlefield[identifier],'menace'):raise ValueError('Menace requires at least two blockers')
   for b in chosen:
    if b in used or b not in blockers or not self.can_block(attackers[identifier],blockers[b]):raise ValueError('Illegal or duplicate blocker')
    used.add(b)
  combat['blocks']={a:list(bs) for a,bs in mapping.items()};combat['blocked']={a for a,bs in mapping.items() if bs}
  self.phase='group_damage_start'
  self.log('block_group','Blockers are declared together.',actor=defender,blocks=combat['blocks'])
  if not self.manual_priority:self.drain_priority(empty_window=True)
 def group_damage_step(self):
  combat=self.group_combat;g=self.event_game('combat')
  live={p.card.id:p for player in self.players for p in player.battlefield if p.card.id in g.battlefield and g.creature(g.battlefield[p.card.id])}
  participants=set(combat['attackers'])|{b for bs in combat['blocks'].values() for b in bs}
  if combat['early'] is None:combat['early']={i for i in participants if i in live and (g.has(g.battlefield[i],'first strike') or g.has(g.battlefield[i],'double strike'))}
  first=self.phase=='group_damage_start' and bool(combat['early']);assignments=[]
  def eligible(i):return i in live and (i in combat['early'] if first else i not in combat['early'] or g.has(g.battlefield[i],'double strike'))
  for identifier in combat['attackers']:
   if identifier not in live:continue
   a=g.battlefield[identifier];blockers=[b for b in combat['blocks'].get(identifier,()) if b in live]
   if eligible(identifier):
    remaining=max(0,g.stats(a)[0]);trample=g.has(a,'trample')
    if blockers:
     for index,b in enumerate(blockers):
      lethal=max(0,g.stats(g.battlefield[b])[1]-live[b].marked_damage)
      if g.has(a,'deathtouch') and lethal:lethal=1
      amount=min(remaining,lethal) if trample or index<len(blockers)-1 else remaining
      assignments.append((identifier,b,amount));remaining-=amount
     if trample:assignments.append((identifier,None,remaining))
    elif identifier not in combat['blocked'] or trample:assignments.append((identifier,None,remaining))
   for b in blockers:
    if eligible(b):assignments.append((b,identifier,max(0,g.stats(g.battlefield[b])[0])))
  touch=set();player_hits=[];damagers={};dealt=[]
  for source,target,amount in assignments:
   source_state=g.battlefield[source]
   if target is not None and g.protected(g.battlefield[target],source_state.definition.colors):amount=0
   if amount<=0:continue
   if target is None:
    defender=self.players[1-self.active];defender.life-=amount;player_hits.append(source)
    card=live[source].card
    if root(card)==self.players[self.active].commander_id:defender.commander_damage[root(card)]=defender.commander_damage.get(root(card),0)+amount
   else:
    live[target].marked_damage+=amount
    if 'Planeswalker' in g.battlefield[target].definition.types and live[target].loyalty is not None:live[target].loyalty=max(0,live[target].loyalty-amount)
    if g.has(source_state,'deathtouch'):touch.add(target)
    damagers.setdefault(target,set()).add(source)
   if g.has(source_state,'lifelink'):self.gain_life(source_state.controller,amount)
   dealt.append(dict(source=source,target=target,amount=amount))
  dead=[]
  for identifier,p in live.items():
   state=g.battlefield[identifier];toughness=g.stats(state)[1]
   if toughness<=0 or ('Planeswalker' in state.definition.types and p.loyalty==0) or (p.marked_damage>=toughness or identifier in touch) and not g.has(state,'indestructible'):
    dead.append((state.controller,p))
  pending=g.aura_damage_triggers(dealt,1-self.active)
  from oracle_abilities import matches
  for identifier in set(player_hits):
   pending.extend(g.combat_draw_triggers(identifier))
   for source in g.battlefield.values():
    for trigger in source.definition.triggers:
     if trigger.event=='combat_damage' and matches(trigger.subject,source,g.battlefield[identifier],True):pending.append(dict(operation='discard',effect='discard',controller=source.controller,name=source.definition.name,source=source.id,target=1-self.active))
  for _,victim in dead:
   for identifier in damagers.get(victim.card.id,()):
    if live[identifier].card.name=='Zurgo Helmsmasher':pending.append(dict(operation='self_counter',effect='add counter',source=identifier,name=live[identifier].card.name,controller=g.battlefield[identifier].controller,amount=1))
  card=next(iter(live.values())).card if live else model(self).Card('combat','Combat','spell')
  self.log('group_damage','Combat damage is simultaneous across the combat.',firstStrike=first,damage=dealt,deaths=[p.card.id for _,p in dead])
  previous=self._resolving_stack;self._resolving_stack=True
  try:
   self.destroy_batch(dead,card,reason='combat_deaths')
   self.resolve_entry_triggers(pending,card)
  finally:self._resolving_stack=previous
  self.resolve_entry_triggers([],card)
  if not self.finished and not self.manual_priority:self.drain_priority(empty_window=True)
  if self.finished:self.group_combat=None;self.pending=None;self.phase='second_main'
  elif first:self.phase='group_regular_damage'
  else:self.phase='second_main';self.pending=None;self.group_combat=None
