from openai import AzureOpenAI
import config as cfg

def generate_chat_completion(prompt, max_tokens=800, temperature=0.7, top_p=0.95, stream=False, client=None, only_content=False):
    """
    生成基于聊天提示的 OpenAI 完成结果
    
    参数:
    - prompt: 聊天提示，可以是文本字符串或者字典列表
      - 如果是文本字符串，则会转换为包含消息字典的格式
    - max_tokens: 生成的最大 token 数
    - temperature: 控制输出的多样性
    - top_p: 基于累计概率进行采样的概率阈值
    
    返回:
    - 完成的生成结果，格式化为 JSON 字符串
    """
    # 判断 prompt 的类型
    if isinstance(prompt, str):
        # 如果 prompt 是字符串，将其转换为包含消息字典的列表
        prompt = [{"role": "user", "content": prompt}]
    elif isinstance(prompt, list):
        # 如果 prompt 是列表，确保每个元素是字典
        for msg in prompt:
            if not isinstance(msg, dict):
                raise ValueError("prompt 列表中的每个元素必须是字典。")
    else:
        raise ValueError("prompt 必须是字符串或字典列表。")

    # 从配置中读取 Azure OpenAI 的参数
    deployment = get_deployment()
    if client is None:
        client = get_client()

    # 生成聊天完成结果
    completion = client.chat.completions.create(
        model=deployment,
        messages=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None,
        stream=stream,
        n=1
    )

    if only_content:
        # 如果只返回内容，则返回生成的文本内容
        return completion.choices[0].message.content
    else:
        return completion

def get_deployment():
    """
    获取 Azure OpenAI 部署名称
    
    返回:
    - Azure OpenAI 部署名称
    """
    return cfg.DEPLOYMENT_NAME

def get_client():
    """
    获取 Azure OpenAI 客户端
    
    返回:
    - Azure OpenAI 客户端
    """
    # 从配置中读取 Azure OpenAI 的参数
    endpoint = cfg.ENDPOINT_URL
    subscription_key = cfg.AZURE_OPENAI_API_KEY

    # 使用基于密钥的身份验证来初始化 Azure OpenAI 客户端
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=subscription_key,
        api_version=cfg.AZURE_API_VERSION,
    )

    return client
