import json
from typing import Tuple
from .blockdata import Binary, RLPList, BInteger, rlpitem, to_json

class BTPHeader(RLPList):
    @rlpitem(0, BInteger)
    def height(self) -> BInteger:
        pass

    @rlpitem(1, BInteger)
    def round(self) -> BInteger:
        pass

    @rlpitem(2, Binary.from_any)
    def next_proof_context_hash(self) -> Binary:
        pass

    def network_section_to_root(self) -> Tuple[Binary]:
        return tuple(map(lambda x: Binary(x), self[3][0]))
    
    @rlpitem(4, BInteger)
    def network_id(self) -> BInteger:
        pass

    @rlpitem(5, BInteger)
    def update_number(self) -> BInteger:
        pass

    def sequence_number(self) -> int:
        return self.update_number()>>1
    
    def is_context_change(self) -> bool:
        return (self.update_number()&0x1) != 0
    
    @rlpitem(6, Binary.from_any)
    def prev(self) -> Binary:
        pass

    @rlpitem(7, BInteger)
    def message_count(self) -> BInteger:
        pass

    @rlpitem(8, Binary.from_any)
    def message_root(self) -> Binary:
        pass

    @rlpitem(9, Binary.from_any)
    def next_proof_context(self) -> Binary:
        pass

    def as_json(self) -> dict:
        return {
            'height': self.height().as_json(),
            'round': self.round().as_json(),
            'nextProofContextHash': to_json(self.next_proof_context_hash()),
            'nid': self.network_id().as_json(),
            'networkSectionToRoot': to_json(self.network_section_to_root()),
            'updateNumber': self.update_number().as_json(),
            'prev': to_json(self.prev()),
            'messageCount': self.message_count().as_json(),
            'messageRoot': to_json(self.message_root()),
            'nextProofContext': to_json(self.next_proof_context()),
        }