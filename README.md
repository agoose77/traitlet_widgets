`traitlet_widgets`
==================

Examples
--------
### Model view
```python
from traitlets import HasTraits, Integer, Unicode
from traitlet_widgets import model_view

class Model(HasTraits):
    name = Unicode()
    age = Integer(min=0)
   
model = Model()

# Output widget:
model_view(model)
```
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