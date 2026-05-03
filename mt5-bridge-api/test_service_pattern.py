"""Test MT5 order through ThreadPoolExecutor with exact service pattern."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import MetaTrader5 as mt5


def _execute_in_thread(fn, *args, **kwargs):
    """Execute MT5 function - simulates MT5Connection.run()"""
    print(f"   Thread: {threading.current_thread().ident}")
    print(f"   Calling: {fn.__name__} args={args} kwargs={kwargs}")
    result = fn(*args, **kwargs)
    print(f"   Result: {result}")
    return result


async def test_service_pattern():
    """Simulate exactly how the FastAPI service calls MT5."""
    print("=" * 60)
    print("TEST: Exact service pattern simulation")
    print("=" * 60)
    
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mt5-worker")
    loop = asyncio.get_event_loop()
    init_thread_id = None
    
    # 1. Initialize in worker thread (like MT5Connection.connect())
    def init_mt5():
        nonlocal init_thread_id
        init_thread_id = threading.current_thread().ident
        print(f"\n1. Initialize MT5 in thread: {init_thread_id}")
        result = mt5.initialize()
        print(f"   initialize() = {result}")
        if result:
            info = mt5.account_info()
            print(f"   Account: {info.login}, Balance: {info.balance}")
        return result
    
    future = executor.submit(init_mt5)
    if not future.result():
        print("FAILED to initialize")
        return
    
    # 2. Get tick price (like _get_execution_price)
    async def get_tick():
        return await loop.run_in_executor(
            executor,
            lambda: _execute_in_thread(mt5.symbol_info_tick, "EURUSDm")
        )
    
    print("\n2. Get tick price:")
    tick = await get_tick()
    if not tick:
        print("FAILED to get tick")
        return
    print(f"   Ask: {tick.ask}")
    
    # 3. Get symbol info (like in open_order)
    async def get_symbol_info():
        return await loop.run_in_executor(
            executor,
            lambda: _execute_in_thread(mt5.symbol_info, "EURUSDm")
        )
    
    print("\n3. Get symbol info:")
    sym_info = await get_symbol_info()
    print(f"   filling_mode: {sym_info.filling_mode}, point: {sym_info.point}")
    
    # 4. Build request dict (exactly like _build_open_request)
    price = round(tick.ask, 5)
    mt5_request = {
        "action": 1,  # mt5.TRADE_ACTION_DEAL
        "symbol": "EURUSDm",
        "volume": 0.01,
        "type": 0,  # mt5.ORDER_TYPE_BUY
        "price": price,
        "deviation": 20,
        "type_filling": 1,  # mt5.ORDER_FILLING_IOC
        "comment": "test-service-pattern",
        "magic": 99999,
    }
    print(f"\n4. Request dict: {mt5_request}")
    
    # 5. Call order_check with keyword argument (like service does)
    async def order_check():
        return await loop.run_in_executor(
            executor,
            lambda: _execute_in_thread(mt5.order_check, request=dict(mt5_request))
        )
    
    print("\n5. order_check() with request=dict:")
    check = await order_check()
    if check:
        print(f"   retcode: {check.retcode}, comment: {check.comment}")
    
    # 6. Call order_send with keyword argument (like service does)
    async def order_send():
        return await loop.run_in_executor(
            executor,
            lambda: _execute_in_thread(mt5.order_send, request=mt5_request)
        )
    
    print("\n6. order_send() with request=kwarg:")
    result = await order_send()
    if result:
        print(f"   retcode: {result.retcode}, comment: {result.comment}")
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"   ✅ SUCCESS! order={result.order}")
    
    # 7. Try direct positional call for comparison
    async def order_send_positional():
        return await loop.run_in_executor(
            executor,
            lambda: mt5.order_send(mt5_request)
        )
    
    print("\n7. order_send() DIRECT positional (no lambda wrapper):")
    result2 = await order_send_positional()
    if result2:
        print(f"   retcode: {result2.retcode}, comment: {result2.comment}")
        if result2.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"   ✅ SUCCESS! order={result2.order}")
    
    # 8. Cleanup
    def shutdown():
        mt5.shutdown()
        print("\n8. MT5 shutdown")
    
    executor.submit(shutdown).result()
    executor.shutdown()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_service_pattern())
