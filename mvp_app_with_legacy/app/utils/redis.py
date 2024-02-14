from typing import Optional
from fastapi import Request, Response
from fastapi_cache import FastAPICache


async def custom_key_builder(
    func,
    namespace: Optional[str] = "",
    request: Request = None,
    response: Response = None,
    *args,
    **kwargs,
):
    prefix = FastAPICache.get_prefix()
    inner_kwargs = kwargs.get('kwargs', {})
    inner_kwargs.pop('db', None)

    if 'req' in inner_kwargs:
        json_data = await inner_kwargs['req'].json()
        inner_kwargs.pop('req', None)
        inner_kwargs['req'] = str(json_data)

    if 'current_user' in inner_kwargs:
        if inner_kwargs['current_user']:
            current_user_id = inner_kwargs['current_user'].id
            inner_kwargs.pop('current_user', None)
            inner_kwargs['current_user'] = str(current_user_id)
        else:
            inner_kwargs.pop('current_user', None)

    kwargs['kwargs'] = inner_kwargs
    cache_key = f"{prefix}:{namespace}:{func.__module__}:{func.__name__}:{args}:{kwargs}"
    return cache_key
