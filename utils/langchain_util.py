def process_graph_and_select_state(graph, config, message_limit=6):
    """
    Process the graph's state history, print details, and select a specific state 
    based on the number of messages.

    :param graph: The input graph containing state history.
    :param config: The configuration object used to fetch state history.
    :param message_limit: The number of messages to use as the selection criterion.
    :return: The selected state if found, otherwise None.
    """
    to_replay = None  # Initialize the selected state as None
    
    for state in graph.get_state_history(config):
        messages_length = len(state.values["messages"])
        message = ''
        
        # Check if there are any messages in the state
        if messages_length > 0:
            last_message = state.values["messages"][messages_length - 1]
            
            # Safely access attributes using getattr
            if getattr(last_message, "tool_calls", None):
                message = f'tool_name: [{last_message.tool_calls[0]["name"]}] args: {last_message.tool_calls[0]["args"]}'
        
        # Print the state details
        print(messages_length, " Next: ", state.next, message)
        print("-" * 80)
        
        # Select the state based on the message limit
        if messages_length == message_limit:
            to_replay = state

    return None
