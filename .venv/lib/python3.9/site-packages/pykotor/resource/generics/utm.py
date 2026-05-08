"""UTM (merchant) generic: GFF-based merchant templates and inventory/pricing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykotor.common.language import LocalizedString
from pykotor.common.misc import Game, InventoryItem, ResRef
from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, read_gff, write_gff
from pykotor.resource.formats.gff.gff_auto import bytes_gff
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from pykotor.resource.formats.gff.gff_data import GFFStruct
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


class UTM:
    """Stores merchant data.

    UTM (User Template Merchant) files define merchant/store blueprints. Stored as GFF format
    with inventory, pricing, and script references. Merchants use UTM templates to define
    their inventory, buy/sell capabilities, and markup/down rates.

    Merchant templates are GFF files with tag, localized name, mark up/down, ``OnOpenStore``,
    ``BuySellFlag`` (buy/sell bits), and ``ItemList`` rows (template ResRef, infinite/droppable
    flags, positions). Observed retail KotOR I and TSL use the same layout; binary/symbol notes
    are migrated to ``wiki/reverse_engineering_findings.md``.

    Note: ``GFFContent.UTM``.

    Attributes:
    ----------
        resref: "ResRef" field. Merchant template ResRef.
            Unique identifier for this merchant template.

        name: "LocName" field. Localized merchant name.
            Display name shown in merchant interface.

        tag: "Tag" field. Merchant tag identifier.
            Used for script references and identification.

        mark_up: "MarkUp" field. Markup percentage for selling to player.
            Percentage added to base item price when player buys.
            Reference: merchants.2da for predefined markup values.

        mark_down: "MarkDown" field. Markdown percentage for buying from player.
            Percentage subtracted from base item price when player sells.
            Reference: merchants.2da for predefined markdown values.

        on_open: "OnOpenStore" field. Script executed when store opens.
            Script ResRef called when merchant interface is opened.

        comment: "Comment" field. Developer comment string.
            Not used by game engine.

        can_buy: Derived from "BuySellFlag" bit 0. Whether merchant can buy items.
            Bit 0: 1 = can buy, 0 = cannot buy.

        can_sell: Derived from "BuySellFlag" bit 1. Whether merchant can sell items.
            Bit 1: 1 = can sell, 0 = cannot sell.

        inventory: "ItemList" field. List of items in merchant inventory.
            Items available for purchase from this merchant.
            Each item has InventoryRes (ResRef), Infinite flag, and position.

        id: "ID" field. Not used by the game engine.
    """

    BINARY_TYPE = ResourceType.UTM

    def __init__(
        self,
        *,
        resref: ResRef = ResRef.from_blank(),
        name: LocalizedString = LocalizedString.from_invalid(),
        tag: str = "",
        mark_up: int = 0,
        mark_down: int = 0,
        on_open: ResRef = ResRef.from_blank(),
        comment: str = "",
        id: int = 5,
        can_buy: bool = False,
        can_sell: bool = False,
        inventory: list[InventoryItem] | None = None,
    ):
        self.resref: ResRef = resref
        self.comment: str = comment
        self.tag: str = tag

        self.name: LocalizedString = name

        self.can_buy: bool = can_buy
        self.can_sell: bool = can_sell

        self.mark_up: int = mark_up
        self.mark_down: int = mark_down

        self.on_open: ResRef = on_open

        self.inventory: list[InventoryItem] = list(inventory) if inventory is not None else []

        # Deprecated:
        self.id: int = id


def construct_utm(
    gff: GFF,
) -> UTM:
    """Constructs a UTM object from a GFF structure.

    Missing fields use blank ResRefs/strings, empty localized name, zero pricing/flags, and an
    empty item list when absent (observed retail).
    """
    utm = UTM()

    root: GFFStruct = gff.root
    utm.resref = root.acquire("ResRef", ResRef.from_blank())
    utm.name = root.acquire("LocName", LocalizedString.from_invalid())
    utm.tag = root.acquire("Tag", "")
    # Pricing/script: zeros and blank ResRef when absent; BuySellFlag decoded to can_buy/can_sell.
    utm.mark_up = root.acquire("MarkUp", 0)
    utm.mark_down = root.acquire("MarkDown", 0)
    utm.on_open = root.acquire("OnOpenStore", ResRef.from_blank())
    utm.comment = root.acquire("Comment", "")
    utm.id = root.acquire("ID", 0)
    utm.can_buy = root.acquire("BuySellFlag", 0) & 1 != 0
    utm.can_sell = root.acquire("BuySellFlag", 0) & 2 != 0

    # ItemList: blank ResRef and flags 0 when absent.
    item_list: GFFList = root.acquire("ItemList", GFFList())
    for item_struct in item_list:
        item = InventoryItem(ResRef.from_blank())
        utm.inventory.append(item)
        item.droppable = bool(item_struct.acquire("Dropable", 0))
        item.resref = item_struct.acquire("InventoryRes", ResRef.from_blank())
        item.infinite = bool(item_struct.acquire("Infinite", 0))

    return utm


def dismantle_utm(
    utm: UTM,
    game: Game = Game.K2,  # noqa: ARG001
    *,
    use_deprecated: bool = True,
) -> GFF:
    gff = GFF(GFFContent.UTM)

    root: GFFStruct = gff.root
    root.set_resref("ResRef", utm.resref)
    root.set_locstring("LocName", utm.name)
    root.set_string("Tag", utm.tag)
    root.set_int32("MarkUp", utm.mark_up)
    root.set_int32("MarkDown", utm.mark_down)
    root.set_resref("OnOpenStore", utm.on_open)
    root.set_string("Comment", utm.comment)
    root.set_uint8("BuySellFlag", utm.can_buy + utm.can_sell * 2)

    item_list: GFFList = root.set_list("ItemList", GFFList())
    for i, item in enumerate(utm.inventory):
        item_struct: GFFStruct = item_list.add(i)
        item_struct.set_resref("InventoryRes", item.resref)
        item_struct.set_uint16("Repos_PosX", i)
        item_struct.set_uint16("Repos_PosY", 0)
        if item.droppable:
            item_struct.set_uint8("Dropable", int(item.droppable))
        if item.infinite:
            item_struct.set_uint8("Infinite", value=True)

    if use_deprecated:
        root.set_uint8("ID", utm.id)

    return gff


def read_utm(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
) -> UTM:
    gff: GFF = read_gff(source, offset, size)
    return construct_utm(gff)


def write_utm(
    utm: UTM,
    target: TARGET_TYPES,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
):
    gff: GFF = dismantle_utm(utm, game, use_deprecated=use_deprecated)
    write_gff(gff, target, file_format)


def bytes_utm(
    utm: UTM,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
) -> bytes:
    gff: GFF = dismantle_utm(utm, game, use_deprecated=use_deprecated)
    return bytes_gff(gff, file_format)
