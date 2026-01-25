"""AutoLabel 模块包。

用于承载所有可注册的 AI 模块，每个模块需实现：
- Init(json): 加载/初始化
- Infer(path, json): 推理
- UnInit(): 卸载/释放

并使用注册器提供的装饰器进行注册。
"""
