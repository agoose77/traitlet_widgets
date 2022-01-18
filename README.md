# Traitlet Widgets
[![pypi-badge][]][pypi] 

[pypi-badge]: https://img.shields.io/pypi/v/traitlet-widgets
[pypi]: https://pypi.org/project/traitlet-widgets

Examples
--------
## Model View
For a given model:
```python
from traitlets import HasTraits, Integer, Unicode

class Model(HasTraits):
    age = Integer(min=0)
    name = Unicode()
```

We can create a view using `model_view`
```python
from traitlet_widgets import model_view

model = Model()
view = model_view(model)
```
which gives  
![Screenshot of result of `model_view`](images/model_view.png)

## UI Customisation
The UI can be customised through the use of `TraitType.tag()` or a custom transformer function.

### Metadata
Any tag set on a trait will be trialed as a widget attribute. If the attribute does not exist on the widget then it will not be set.
For example:
```python
from traitlets import HasTraits, Integer, Unicode
from traitlet_widgets import model_view

class Model(HasTraits):
    age = Integer(min=0)
    name = Unicode().tag(description="A girl has no name")

model = Model()

model_view(model)
```

![Screenshot of result of `model_view`](images/model_view_tag.png)

The same metadata that can be provided using tags can also be provided through a
 hierarchical metadata dictionary:
```python
model_view(model, metadata={"name": {"description": "Model name meta"}})
```
This may be desired if it is important to hide UI details from the model.
 
### Variants

It is possible to override the variant used for a particular trait, provided it is compatible with the underlying trait:
```python
from traitlets import HasTraits, Integer, Unicode
from traitlet_widgets import  model_view

class Model(HasTraits):
    age = Integer(min=0, max=10)
    name = Unicode()

model_view(Model())
```
![Screenshot of result of `model_view`](images/model_view_slider.png)

Let's create a bounded integer text view for the age field:
```python
from traitlets import HasTraits, Integer, Unicode
from traitlet_widgets import  model_view
import ipywidgets as widgets

class Model(HasTraits):
    age = Integer(min=0, max=10).tag(variant=widgets.BoundedIntText)
    name = Unicode()

model_view(Model())
```
![Screenshot of result of `model_view`](images/model_view_bounded.png)


### Advanced Usage
To further control how a view is generated from a model, you can subclass the view
factory. For example, given this model
```python
from traitlets import HasTraits, Integer, Unicode
from traitlet_widgets import  model_view
import ipywidgets as widgets

class Model(HasTraits):
    age = Integer(min=0, max=10).tag(variant=widgets.BoundedIntText)
    name = Unicode()

model_view(Model())
```
we can create a custom view factory:
```python
from traitlet_widgets import ViewFactory

class CustomFactory(ViewFactory):

    def create_trait_view(self, trait, ctx):
        default_widget = super().create_trait_view(trait, ctx)

        if ctx.name == "name":
            default_widget.description = "A girl has no name"
            default_widget.style = {"description_width": "initial"}

        return default_widget

f = CustomFactory()
f.create_root_view(Model())
```

![Screenshot of result of `model_view`](images/model_view_tag.png)

### Adding custom widgets
With the `trait_view_variants` decorator, it is possible to register custom view
variants for a particular trait type, for example:
```python
from traitlet_widgets import trait_view_variants
import ipywidgets as widgets
import traitlets

@trait_view_variants(traitlets.Bool)
def bool_view_factory(trait, ctx):
    yield widgets.ToggleButton, ctx.metadata
    ...
```

But sometimes you might wish to forgo the metadata-driven UI, and directly
specify the factory and its arguments. For this, you can use the `factory` metadata
field:
```python
from traitlets import HasTraits, Integer, Unicode
from traitlet_widgets import model_view
import ipywidgets as widgets


class Model(HasTraits):
    age = Integer(min=0, max=10)
    name = Unicode()


def play_factory(trait, ctx):
    return widgets.Play, {
        "min": trait.get("min", 0),
        "max": trait.get("max", 100),
        **ctx.metadata,
    }


model_view(Model(), metadata={"age": {"factory": play_factory}})

```

### Further Customisation
Although this library is driven by metadata, it is possible to modify this
behaviour by overriding the appropriate methods on the view factory.
These methods govern the trait discovery, view creation, and trait filtering. 
