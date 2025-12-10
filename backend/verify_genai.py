

from google.genai import types

def verify():
    tool_name = "initialize_network"
    tool_desc = "Initializes a network from GraphML data."
    tool_schema = {'properties': {'network_id': {'title': 'Network Id', 'type': 'integer'}, 'graphml_data': {'title': 'Graphml Data', 'type': 'string'}}, 'required': ['network_id', 'graphml_data'], 'title': 'initialize_networkArguments', 'type': 'object'}
    
    print(f"Creating FunctionDeclaration with name='{tool_name}'")
    
    fd = types.FunctionDeclaration(
        name=tool_name,
        description=tool_desc,
        parameters=tool_schema
    )
    
    print(f"FunctionDeclaration: {fd}")
    
    print("Creating Tool wrapping it...")
    tool = types.Tool(function_declarations=[fd])
    print(f"Tool: {tool}")
    
    # Simulate what service.py does
    print("Creating GenerateContentConfig...")
    config = types.GenerateContentConfig(
        tools=[tool],
        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="AUTO"))
    )
    print("Config created successfully.")

if __name__ == "__main__":
    verify()
