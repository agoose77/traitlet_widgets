from typing import Any, Callable, Dict, Iterator, Optional, Type, Tuple, Union
import ipywidgets as widgets
import traitlets

FilterType = Callable[
    [Type[traitlets.HasTraits], Tuple[str, ...], traitlets.TraitType], bool
]


VariantIterator = Iterator[Tuple[Type[widgets.Widget], Dict[str, Any]]]
TraitViewFactoryType = Callable[
    [traitlets.TraitType, Dict[str, Any], "ViewFactoryContext"], VariantIterator
]
_trait_view_variant_factories: Dict[
    Type[traitlets.TraitType], TraitViewFactoryType
] = {}
