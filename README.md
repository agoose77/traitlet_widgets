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

There is also a `model_view_for` function to generate the view class from the model class:
```python
from traitlet_widgets import model_view_for

model = Model()
view = model_view_for(Model)
view.model = model
```
This is more efficient in the case that there are multiple views of the same model.

## UI Customisation
The UI can be customised through the use of `TraitType.tag()` or a custom visitor function.

### Tags
Any tag set on a trait will be trialled as a widget attribute. If the attribute does not exist on the widget then it will not be set.
For example:
```python
from traitlets import HasTraits, Integer, Unicode

class Model(HasTraits):
    name = Unicode().tag(description="Model name")
    age = Integer(min=0)

view = model_view(Model())
```

![Screenshot of result of `model_view`](images/model_view_tag.png)

### Visitors
```python
from traitlets import HasTraits, Integer, Unicode

class Model(HasTraits):
    name = Unicode()
    age = Integer(min=0)

def visit_trait(model, path, trait, widget):
    if path[-1] == "name":
        widget.description = "Model name"

view = model_view(Model(), visitor=visit_trait)
```

![Screenshot of result of `model_view`](images/model_view_tag.png)
