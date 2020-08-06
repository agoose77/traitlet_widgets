`traitlet_widgets`
==================

Examples
--------
## Model view
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
