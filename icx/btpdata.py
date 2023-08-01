import json
from typing import Tuple
from .blockdata import Binary, RLPList, BInteger, rlpitem

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
        return tuple(map(lambda x: Binary(x), self[3]))
    
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

    def to_json(self) -> dict:
        return {
            'height': self.height().to_json(),
            'round': self.round().to_json(),
            'nextProofContextHash': Binary.to_json(self.next_proof_context_hash()),
            'nid': self.network_id().to_json(),
            'networkSectionToRoot': tuple(map(
                lambda x: Binary.to_json(x),
                self.network_section_to_root()
            )),
            'updateNumber': self.update_number().to_json(),
            'prev': Binary.to_json(self.prev()),
            'messageCount': self.message_count().to_json(),
            'messageRoot': Binary.to_json(self.message_root()),
            'nextProofContext': Binary.to_json(self.next_proof_context()),
        }