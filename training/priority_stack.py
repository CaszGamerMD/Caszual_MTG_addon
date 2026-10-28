"""Two-player priority and LIFO resolution. No game effects are executed here."""
from dataclasses import dataclass

@dataclass(frozen=True)
class StackItem:
    id: int
    controller: int
    payload: object
    label: str

class PriorityStack:
    def __init__(self,active=0):
        self.active=active;self.priority=active;self.passes=0;self.items=[];self.sequence=0
    def push(self,controller,payload,label,actor=None):
        if controller not in (0,1): raise ValueError('Invalid controller')
        if actor is not None and actor!=self.priority: raise ValueError('Actor lacks priority')
        self.sequence+=1
        item=StackItem(self.sequence,controller,payload,label)
        self.items.append(item);self.passes=0
        if actor is not None: self.priority=actor
        return item
    def pass_priority(self,actor):
        if actor!=self.priority: raise ValueError('Actor lacks priority')
        self.passes+=1
        if self.passes<2:
            self.priority=1-actor
            return 'pass',None
        self.passes=0;self.priority=self.active
        if self.items: return 'resolve',self.items.pop()
        return 'advance',None
    def counter(self,identifier):
        for i,item in enumerate(self.items):
            if item.id==identifier: return self.items.pop(i)
        return None
    def public(self):
        return [{'id':i.id,'controller':i.controller,'label':i.label} for i in self.items]
