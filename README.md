`traitlet_widgets`
==================

Examples
--------
### Model view
#### Create Model
```python
from traitlets import HasTraits, Integer, Unicode
from traitlet_widgets import model_view

class Model(HasTraits):
    name = Unicode()
    age = Integer(min=0)
```
#### View Model
```python
# Output widget:
model = Model()
view = model_view(model)
view.model = model
```
#### Alternative API
```python
# Output widget:
view = model_view_for(Model)
model = Model()
view.model = model
```
![Screenshot of result of `model_view`](images/model_view.png)

### Model observer
```python
from traitlets import HasTraits, Integer, Unicode
from traitlet_widgets import model_observer

class Model(HasTraits):
    name = Unicode()
    age = Integer(min=0)
   
model = Model()

@model_observer(model)
def on_model_changed(name, age):
    print(f"{name} is {age} years old!") 
    
model.name = "Jack"
model.age = 12
```
Which gives
```
Jack is 0 years old!
Jack is 12 years old!
```
