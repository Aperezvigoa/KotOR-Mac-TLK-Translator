# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class Vis(KaitaiStruct):
    """VIS (Visibility) files describe which module rooms can be seen from other rooms.
    They drive the engine's occlusion culling so that only geometry visible from the
    player's current room is rendered, reducing draw calls and overdraw.
    
    Format Overview:
    - VIS files are plain ASCII text
    - Each parent room line lists how many child rooms follow
    - Child room lines are indented by two spaces
    - Empty lines are ignored and names are case-insensitive
    - Files usually ship as moduleXXX.vis pairs
    
    File Layout:
    - Parent Lines: "ROOM_NAME CHILD_COUNT"
    - Child Lines: "  ROOM_NAME" (indented with 2 spaces)
    - Version headers (e.g., "room V3.28") are skipped
    - Empty lines are ignored
    
    Example:
    ```
    room012 3
      room013
      room014
      room015
    ```
    
    Parsing Rules:
    1. Lines are processed sequentially
    2. Empty lines (whitespace only) are ignored
    3. Version header lines (second token starts with "V") are skipped
    4. Parent lines contain room name and child count (e.g., "room012 3")
    5. Child lines are indented with 2 spaces and contain room name
    6. After a parent line, exactly CHILD_COUNT child lines must follow
    7. Room names are case-insensitive (stored lowercase)
    
    Runtime Behavior:
    - When the player stands in room A, the engine renders any room listed under A
    - VIS files only control visibility; collision and pathfinding rely on walkmeshes
    - Editing VIS entries is a common optimization for performance
    - Missing VIS files cause all rooms to render (performance impact)
    
    Performance Impact:
    - Without VIS: Engine renders all rooms, even those behind walls/doors
    - With VIS: Only visible rooms are submitted to the renderer (10-50x fewer draw calls)
    - Overly restrictive VIS: Causes pop-in where rooms suddenly appear
    - Too permissive VIS: Wastes GPU resources rendering unseen geometry
    
    Common Issues:
    - Missing Room: Room not in any VIS list → never renders → appears invisible
    - One-way Visibility: Room A lists B, but B doesn't list A → asymmetric rendering
    - Performance Problems: All rooms list each other → defeats purpose of VIS optimization
    - Doorway Artifacts: Door rooms not mutually visible → walls clip during door animations
    
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(Vis, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.raw_content = (self._io.read_bytes_full()).decode(u"ASCII")


    def _fetch_instances(self):
        pass


