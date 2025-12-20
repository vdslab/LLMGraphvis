import inspect

from google.genai import types

print("types.GenerateContentConfig signature:")
try:
    print(inspect.signature(types.GenerateContentConfig))
except Exception as e:
    print(e)

print("\ntypes.Tool signature:")
try:
    print(inspect.signature(types.Tool))
except Exception as e:
    print(e)

print("\ntypes.FunctionDeclaration signature:")
try:
    print(inspect.signature(types.FunctionDeclaration))
except Exception as e:
    print(e)

print("\nTool attributes:")
print([x for x in dir(types.Tool) if not x.startswith("_")])
