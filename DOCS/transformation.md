# Intro
In some cases additional internal logic is required for additional transformation before the data is written to Splunk from one of the fetchers.

In order to support that the code will dynamically load a transformation if one exists (see [Bamboo](pipeline/bamboo.py#L36)):

```python
transform_logic = importlib.util.find_spec('internal.bamboo')

if (transform_logic is not None):
    from internal.bamboo import transform
else:
    transform = None
```

The same mechanism could be used in other fetchers to allow additional customisation.
