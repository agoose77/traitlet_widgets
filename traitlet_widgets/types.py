from typing import Any, Callable, Dict, Iterator, Type, Tuple
import ipywidgets as widgets
import traitlets

FilterType = Callable[
    [Type[traitlets.HasTraits], Tuple[str, ...], traitlets.TraitType], bool
]


VariantIterator = Iterator[Tuple[Type[widgets.Widget], Dict[str, Any]]]
TraitViewFactoryType = Callable[
    [traitlets.TraitType, "ViewFactoryContext"], VariantIterator
]
_trait_view_variant_factories: Dict[
    Type[traitlets.TraitType], TraitViewFactoryType
] = {}
