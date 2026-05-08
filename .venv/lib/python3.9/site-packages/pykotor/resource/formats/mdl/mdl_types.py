"""Type definitions for MDL/MDX files.

This module contains ONLY enums, flags, and constants used across the MDL/MDX format stack.
The canonical runtime MDL object model (classes with __eq__/__hash__/methods) lives in
`pykotor.resource.formats.mdl.mdl_data`.

For working with MDL models, import from:
    from pykotor.resource.formats.mdl import MDL, MDLNode, MDLMesh, MDLAnimation, ...

Architecture:
    - mdl_types.py: Enums, flags, constants (THIS FILE)
    - mdl_data.py: Runtime classes (MDL, MDLNode, MDLMesh, etc.) with full functionality
    - io_mdl.py: Binary MDL/MDX reader/writer
    - io_mdl_ascii.py: ASCII MDL reader/writer (MDLOps-compatible format)
    - mdl_auto.py: Format detection and dispatch

Observed retail behavior:
    KotOR I and TSL load paired ``.mdl`` / ``.mdx`` resources through the same Aurora-style
    model pipeline other Odyssey titles use. It has been observed that the games deduplicate
    models by name when reloading and accept the node flag and controller layouts reflected
    in the enums below.

    Maintainers: superseded MDL/MDX implementation tables are **migrated** to the wiki
    engine-findings article (*PyKotor package: migrated library notes* and linked MDL appendix
    pages). Third-party tool URLs (MDLOps, kotorblender anchors) removed from this file are
    archived at ``wiki/reverse_engineering_findings_mdl_types_github_urls_pre_scrub.md``.
"""

from __future__ import annotations

from enum import IntEnum, IntFlag


# region Enums and Flags
class MDLGeometryType(IntEnum):
    """Model geometry type indicating how it should be rendered."""

    GEOMETRY_UNKNOWN = 0
    GEOMETRY_NORMAL = 1
    GEOMETRY_SKINNED = 2
    GEOMETRY_DANGLY = 3
    GEOMETRY_SABER = 4

    # Back-compat aliases (older engine/tooling code used PascalCase names).
    # Keep these as enum aliases so `MDLGeometryType.Model` continues to work.
    Model = GEOMETRY_NORMAL
    Skinned = GEOMETRY_SKINNED
    Dangly = GEOMETRY_DANGLY
    Saber = GEOMETRY_SABER


class MDLClassification(IntEnum):
    """Model classification indicating its usage in the game."""

    INVALID = 0  # 0x0
    EFFECT = 1  # 0x1
    TILE = 2  # 0x2
    CHARACTER = 4  # 0x4
    DOOR = 8  # 0x8
    PLACEABLE = 16  # 0x10
    OTHER = 32  # 0x20
    GUI = 64  # 0x40
    ITEM = 128  # 0x80
    LIGHTSABER = 256  # 0x100
    WAYPOINT = 512  # 0x200
    WEAPON = 1024  # 0x400
    FURNITURE = 2048  # 0x800


class MDLNodeFlags(IntFlag):
    """Node flags indicating what type of data is attached to the node.

    These flags are combined to create specific node types. For example:
    - mesh = HEADER + MESH = 0x021 = 33
    - skin mesh = HEADER + MESH + SKIN = 0x061 = 97
    - dangly mesh = HEADER + MESH + DANGLY = 0x121 = 289
    - aabb mesh = HEADER + MESH + AABB = 0x221 = 545
    - saber mesh = HEADER + MESH + SABER = 0x821 = 2081

    The bitmask combinations below match how retail KotOR builds classify nodes (tri-mesh,
    skin, dangly, saber, AABB, emitter, light, reference).

    """

    # Base node flags
    HEADER = 0x0001  # NODE_HAS_HEADER - Base node data (mdlops:302)
    LIGHT = 0x0002  # NODE_HAS_LIGHT - Light data (mdlops:303, kotorblender:94)
    EMITTER = 0x0004  # NODE_HAS_EMITTER - Particle emitter data (mdlops:304, kotorblender:95)
    CAMERA = 0x0008  # NODE_HAS_CAMERA - Camera data (not in mdlops quick ref)
    REFERENCE = (
        0x0010  # NODE_HAS_REFERENCE - Reference to another model (mdlops:305, kotorblender:96)
    )
    MESH = 0x0020  # NODE_HAS_MESH - Mesh geometry (mdlops:306, kotorblender:97)
    SKIN = 0x0040  # NODE_HAS_SKIN - Skinned mesh (mdlops:307, kotorblender:98)
    ANIM = 0x0080  # NODE_HAS_ANIM - Animation mesh (mdlops:308)
    DANGLY = 0x0100  # NODE_HAS_DANGLY - Cloth/hair physics mesh (mdlops:309, kotorblender:99)
    AABB = 0x0200  # NODE_HAS_AABB - Walkmes/collision data (mdlops:310, kotorblender:100)
    SABER = 0x0800  # NODE_HAS_SABER - Lightsaber blade mesh (mdlops:311, kotorblender:101)


class MDLNodeType(IntEnum):
    """Node types indicating the role of the node in the model."""

    DUMMY = 1  # Empty node for hierarchy
    TRIMESH = 2  # Basic mesh
    DANGLYMESH = 3  # Physics-enabled mesh
    LIGHT = 4  # Light source
    EMITTER = 5  # Particle emitter
    REFERENCE = 6  # Reference to another model
    PATCH = 7  # NURBS patch (unused)
    AABB = 8  # Axis-aligned bounding box
    SKIN = 9  # Skinned mesh (mdlops:320, NODE_SKIN = 97 = HEADER + MESH + SKIN flags)
    CAMERA = 10  # Camera viewpoint
    BINARY = 11  # Binary (unknown usage)
    SABER = 12  # Lightsaber blade


# region Controller Data
class MDLControllerType(IntEnum):
    """Controller types for animations and node properties.

    These controller types are used to animate various properties of nodes in MDL models.
    Controllers can be indexed by node type since some IDs are reused for different node types.

    Controller IDs follow the Aurora/KotOR layout documented in vendor tooling; some numeric
    IDs are overloaded per node kind.


    Note: Controller indexing by node type is necessary because at least one controller ID (100)
    """

    INVALID = -1

    # Base node controllers (NODE_HAS_HEADER)
    POSITION = 8  # position - All nodes (mdlops:329)
    ORIENTATION = 20  # orientation - All nodes (mdlops:330)
    SCALE = 36  # scale - All nodes (mdlops:331)
    ALPHA = 132  # alpha - All nodes (mdlops:332, was 128)

    # Light controllers (NODE_HAS_LIGHT)
    COLOR = 76  # color - Light nodes (mdlops:342)
    RADIUS = 88  # radius - Light nodes (mdlops:343)
    SHADOWRADIUS = 96  # shadowradius - Light nodes (mdlops:344)
    VERTICALDISPLACEMENT = 100  # verticaldisplacement - Light nodes (mdlops:345)
    MULTIPLIER = 140  # multiplier - Light nodes (mdlops:346)

    # Emitter controllers (NODE_HAS_EMITTER)
    # These mappings were updated based on fx_flame01.mdl analysis (mdlops:352-355)
    ALPHAEND = 80  # alphaEnd - Emitter (mdlops:357)
    ALPHASTART = 84  # alphaStart - Emitter (mdlops:358)
    BIRTHRATE = 88  # birthrate - Emitter (mdlops:359, same as RADIUS for lights)
    BOUNCECO = 92  # bounce_co - Emitter (mdlops:360)
    COMBINETIME = 96  # combinetime - Emitter, was 120 (mdlops:361)
    DRAG = 100  # drag - Emitter (mdlops:362, same as VERTICALDISPLACEMENT for lights)
    FPS = 104  # fps - Emitter, was 128 (mdlops:363)
    FRAMEEND = 108  # frameEnd - Emitter, was 132 (mdlops:364)
    FRAMESTART = 112  # frameStart - Emitter, was 136 (mdlops:365)
    GRAV = 116  # grav - Emitter, was 140 (mdlops:366)
    LIFEEXP = 120  # lifeExp - Emitter, was 144 (mdlops:367)
    MASS = 124  # mass - Emitter, was 148 (mdlops:368)
    P2P_BEZIER2 = 128  # p2p_bezier2 - Emitter, was 152 (mdlops:369)
    P2P_BEZIER3 = 132  # p2p_bezier3 - Emitter, was 156 (mdlops:370)
    PARTICLEROT = 136  # particleRot - Emitter, was 160 (mdlops:371)
    RANDVEL = 140  # randvel - Emitter, was 164 (mdlops:372)
    SIZESTART = 144  # sizeStart - Emitter, was 168 (mdlops:373)
    SIZEEND = 148  # sizeEnd - Emitter, was 172 (mdlops:374)
    SIZESTART_Y = 152  # sizeStart_y - Emitter, was 176 (mdlops:375)
    SIZEEND_Y = 156  # sizeEnd_y - Emitter, was 180 (mdlops:376)
    SPREAD = 160  # spread - Emitter, was 184 (mdlops:377)
    THRESHOLD = 164  # threshold - Emitter, was 188 (mdlops:378)
    VELOCITY = 168  # velocity - Emitter, was 192 (mdlops:379)
    XSIZE = 172  # xsize - Emitter, was 196 (mdlops:380)
    YSIZE = 176  # ysize - Emitter, was 200 (mdlops:381)
    BLURLENGTH = 180  # blurlength - Emitter, was 204 (mdlops:382)
    LIGHTNINGDELAY = 184  # lightningDelay - Emitter, was 208 (mdlops:383)
    LIGHTNINGRADIUS = 188  # lightningRadius - Emitter, was 212 (mdlops:384)
    LIGHTNINGSCALE = 192  # lightningScale - Emitter, was 216 (mdlops:385)
    LIGHTNINGSUBDIV = 196  # lightningSubDiv - Emitter (mdlops:386)
    LIGHTNINGZIGZAG = 200  # lightningzigzag - Emitter (mdlops:387)
    ALPHAMID = 216  # alphaMid - Emitter, was 464 (mdlops:388)
    PERCENTSTART = 220  # percentStart - Emitter, was 480 (mdlops:389)
    PERCENTMID = 224  # percentMid - Emitter, was 481 (mdlops:390)
    PERCENTEND = 228  # percentEnd - Emitter, was 482 (mdlops:391)
    SIZEMID = 232  # sizeMid - Emitter, was 484 (mdlops:392)
    SIZEMID_Y = 236  # sizeMid_y - Emitter, was 488 (mdlops:393)
    RANDOMBIRTHRATE = 240  # m_fRandomBirthRate - Emitter (mdlops:394)
    TARGETSIZE = 252  # targetsize - Emitter (mdlops:395)
    NUMCONTROLPTS = 256  # numcontrolpts - Emitter (mdlops:396)
    CONTROLPTRADIUS = 260  # controlptradius - Emitter (mdlops:397)
    CONTROLPTDELAY = 264  # controlptdelay - Emitter (mdlops:398)
    TANGENTSPREAD = 268  # tangentspread - Emitter (mdlops:399)
    TANGENTLENGTH = 272  # tangentlength - Emitter (mdlops:400)
    COLORMID = 284  # colorMid - Emitter, was 468 (mdlops:401)
    COLOREND = 380  # colorEnd - Emitter, was 96 (mdlops:402)
    COLORSTART = 392  # colorStart - Emitter, was 108 (mdlops:403)
    DETONATE = 502  # detonate - Emitter, was 228 (mdlops:404)

    # Mesh controllers (NODE_HAS_MESH)
    SELFILLUMCOLOR = (
        100  # selfillumcolor - Mesh (mdlops:406, same as DRAG and VERTICALDISPLACEMENT)
    )

    # Legacy aliases for backward compatibility
    BOUNCE_CO = BOUNCECO
    P2P_BEZIER_2 = P2P_BEZIER2
    ILLUM_COLOR = SELFILLUMCOLOR
    ILLUM = SELFILLUMCOLOR
    SIZESTART_emitter = SIZESTART
    SIZEEND_emitter = SIZEEND
    LIGHTNINGDELAY_emitter = LIGHTNINGDELAY
    LIGHTNINGRADIUS_emitter = LIGHTNINGRADIUS
    LIGHTNINGSCALE_emitter = LIGHTNINGSCALE
    ALPHAMID_emitter = ALPHAMID
    SIZEMID_emitter = SIZEMID
    DETONATE_emitter = DETONATE

    # Additional back-compat aliases (PascalCase) used by PyKotorEngine tests/tooling.
    Position = POSITION
    Orientation = ORIENTATION
    Scale = SCALE
    Alpha = ALPHA
    Color = COLOR
    Radius = RADIUS
    Multiplier = MULTIPLIER

    # NOTE: Some controller IDs that were previously defined have been removed or
    # corrected based on vendor analysis. See fx_flame01.mdl analysis in mdlops:352-355


class MDLTrimeshProps(IntFlag):
    """Properties for trimesh nodes."""

    NONE = 0x00
    LIGHTMAP = 0x01
    COMPRESSED = 0x02
    UNKNOWN = 0x04
    TANGENTS = 0x08
    UNKNOWNA = 0x10
    UNKNOWNB = 0x20
    UNKNOWNC = 0x40
    UNKNOWND = 0x80


class MDLEmitterType(IntEnum):
    """Types of particle emitters."""

    STATIC = 0
    FIRE = 1
    FOUNTAIN = 2
    LIGHTNING = 3


class MDLRenderType(IntEnum):
    """Particle rendering types."""

    NORMAL = 0
    LINKED = 1
    BILLBOARD_TO_LOCAL_Z = 2
    BILLBOARD_TO_WORLD_Z = 3
    ALIGNED_TO_WORLD_Z = 4
    ALIGNED_TO_PARTICLE_DIR = 5
    MOTION_BLUR = 6


class MDLBlendType(IntEnum):
    """Particle blend modes."""

    NORMAL = 0
    PUNCH = 1
    LIGHTEN = 2
    MULTIPLY = 3


class MDLUpdateType(IntEnum):
    """Particle update modes."""

    FOUNTAIN = 0
    SINGLE = 1
    EXPLOSION = 2
    LIGHTNING = 3


class MDLTrimeshFlags(IntFlag):
    """Additional trimesh flags from KotOR implementation.

    Flags mirror shipped MDL content seen in retail modules.
    """

    TILEFADE = 0x0001  # Has tile fade
    HEAD = 0x0002  # Is a head mesh
    RENDER = 0x0004  # Should be rendered
    SHADOW = 0x0008  # Casts shadows
    BEAMING = 0x0010  # Has beaming
    RENDER_ENV_MAP = 0x0020  # Should render environment mapping
    LIGHTMAP = 0x0040  # Has lightmap
    SKIN = 0x0080  # Is skinned mesh


class MDLLightFlags(IntFlag):
    """Light flags from KotOR implementation.

    Values align with lights emitted from MDL light nodes in shipped data.
    """

    ENABLED = 0x0001  # Light is enabled
    SHADOW = 0x0002  # Light casts shadows
    FLARE = 0x0004  # Light has lens flare
    FADING = 0x0008  # Light is fading
    AMBIENT = 0x0010  # Light is ambient only


class MDLEmitterFlags(IntFlag):
    """Particle emitter behavior flags.

    These flags control various aspects of particle emitter behavior including physics,
    inheritance, and rendering properties.

    """

    P2P = 0x0001  # EMITTER_FLAG_P2P - Point-to-point emitter (kotorblender:115)
    P2P_SEL = 0x0002  # EMITTER_FLAG_P2P_SEL - P2P selection (kotorblender:116)
    P2P_BEZIER = 0x0002  # P2P with Bezier curves (alias of P2P_SEL)
    AFFECTED_WIND = 0x0004  # EMITTER_FLAG_AFFECTED_WIND - Affected by wind (kotorblender:117)
    TINTED = 0x0008  # EMITTER_FLAG_TINTED - Particles are tinted (kotorblender:118)
    BOUNCE = 0x0010  # EMITTER_FLAG_BOUNCE - Particles bounce on collision (kotorblender:119)
    RANDOM = 0x0020  # EMITTER_FLAG_RANDOM - Random rotation (kotorblender:120)
    INHERIT = 0x0040  # EMITTER_FLAG_INHERIT - Inherit parent orientation (kotorblender:121)
    INHERIT_VEL = 0x0080  # EMITTER_FLAG_INHERIT_VEL - Inherit parent velocity (kotorblender:122)
    INHERIT_LOCAL = (
        0x0100  # EMITTER_FLAG_INHERIT_LOCAL - Inherit local transform (kotorblender:123)
    )
    SPLAT = 0x0200  # EMITTER_FLAG_SPLAT - Splat on collision (kotorblender:124)
    INHERIT_PART = (
        0x0400  # EMITTER_FLAG_INHERIT_PART - Inherit particle properties (kotorblender:125)
    )
    DEPTH_TEXTURE = 0x0800  # EMITTER_FLAG_DEPTH_TEXTURE - Use depth texture (kotorblender:126)
    FLAG_13 = 0x1000  # Unknown flag 13 (kotorblender:127)

    # Legacy aliases
    LOOP = P2P  # Backward compatibility


class MDLSaberFlags(IntFlag):
    """Lightsaber mesh flags (on-disk / tool-agreed bitmask)."""

    FLARE = 0x0001  # Has flare effect
    DYNAMIC = 0x0002  # Dynamic lighting
    TRAIL = 0x0004  # Has motion trail


class MDLDynamicType(IntEnum):
    """Dynamic types for lights."""

    STATIC = 0
    DYNAMIC = 1
    ANIMATED = 2


# endregion
