`traitlet_widgets`
==================

Examples
--------
## Model View
For a given model:
```python
from traitlets import HasTraits, Integer, Unicode

class Model(HasTraits):
    name = Unicode()
    age = Integer(min=0)
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

### Tags
Any tag set on a trait will be trialled as a widget attribute. If the attribute does not exist on the widget then it will not be set.
For example:
```python
from traitlets import HasTraits, Integer, Unicode
from traitlet_widgets import model_view

class Model(HasTraits):
    name = Unicode().tag(description="Model name")
    age = Integer(min=0)

model_view(Model())
```

![Screenshot of result of `model_view`](images/model_view_tag.png)

### Transformers
Transformers can be used to modify the widgets rendered by the library. This can be used to modify widgets:
```python
from traitlets import HasTraits, Integer, Unicode
from traitlet_widgets import model_view

class Model(HasTraits):
    name = Unicode()
    age = Integer()

def transform_trait(model, trait, widget, ctx):
    if ctx.name == "name":
        widget.description = "Model name"

model_view(Model(), transform_trait=transform_trait)
```

![Screenshot of result of `model_view`](images/model_view_tag.png)

It is also possible to override the variant used for a particular trait, provided it is compatible with the underlying trait:
```python
from traitlets import HasTraits, Integer, Unicode
from traitlet_widgets import  model_view

class Model(HasTraits):
    name = Unicode()
    age = Integer(min=0, max=10)

model_view(Model())
```

![Screenshot of result of `model_view`](images/model_view_slider.png)

```python
import ipywidgets as widgets

def transform_trait(model, trait, widget, ctx):
    if ctx.name == "age":
        # Create a bounded int text instead of a slider
        return ctx.create_trait_view(
            trait, {"variant": widgets.BoundedIntText, "description": ctx.display_name}
        )


model_view(Model(), transform_trait=transform_trait)
```

![Screenshot of result of `model_view`](images/model_view_bounded.png)

This approach may be preferred if there is a desire to remove UI descriptions from the model.

### Further Customisation
Through the transformer mechanism, the `ViewFactoryContext` context object can be used to create particular widget variants and customised widgets. Alternatively, you can inject your own widgets here simply by returning them.
All widgets are linked to the underlying model through the `value` trait. The widget must also provide `disabled` and `description` traits. 