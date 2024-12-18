import time
import json
import hashlib
import hmac
import requests


def _create_sign(path: str, bodymod: str = None, params: dict = None):
    header = dict()
    apikey = "51858a3b-14b7-4357-8d33-69b9dbc0505d"
    secret = "c66fc1734b784415d23e787cca918f8b2075509e"
    timestamp = str(int(time.time() * 1000))
    if bodymod == 'application/x-www-form-urlencoded':
        if params:
            params = dict(sorted(params.items(), key=lambda e: e[0]))
            message = "&".join([f"{arg}={params[arg]}" for arg in params])
            signkey = f"xt-validate-appkey={apikey}&xt-validate-timestamp={timestamp}#{path}#{message}"
        else:
            signkey = f"xt-validate-appkey={apikey}&xt-validate-timestamp={timestamp}#{path}"
    elif bodymod == 'application/json':
        if params:
            message = json.dumps(params)
            signkey = f"xt-validate-appkey={apikey}&xt-validate-timestamp={timestamp}#{path}#{message}"
        else:
            signkey = f"xt-validate-appkey={apikey}&xt-validate-timestamp={timestamp}#{path}"
    else:
        assert False, f"not support this bodymod:{bodymod}"

    digestmodule = hashlib.sha256
    sign = hmac.new(secret.encode("utf-8"), signkey.encode("utf-8"), digestmod=digestmodule).hexdigest()
    header.update({
        'validate-signversion': "2",
        'xt-validate-appkey': apikey,
        'xt-validate-timestamp': timestamp,
        'xt-validate-signature': sign,
        'xt-validate-algorithms': "HmacSHA256"
    })
    return header


def _fetch(method, url, params=None, body=None, data=None, headers=None, timeout=30, **kwargs):
    """
    Create a HTTP request.
       Args:
           method: HTTP request method. `GET` / `POST` / `PUT` / `DELETE`
           url: Request url.
           params: HTTP query params.
           body: HTTP request body, string or bytes format.
           data: HTTP request body, dict format.
           headers: HTTP request header.
           timeout: HTTP request timeout(seconds), default is 30s
           kwargs:
               proxy: HTTP proxy.

       Return:
           code: HTTP response code.
           success: HTTP response data. If something wrong, this field is None.
           error: If something wrong, this field will holding a Error information, otherwise it's None.

       Raises:
           HTTP request exceptions or response data parse exceptions. All the exceptions will be captured and return
           Error information.
    """
    try:
        if method == "GET":
            response = requests.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
        elif method == "POST":
            response = requests.post(url, params=params, data=body, json=data, headers=headers,
                                     timeout=timeout, **kwargs)
        elif method == "PUT":
            response = requests.put(url, params=params, data=body, json=data, headers=headers,
                                    timeout=timeout, **kwargs)
        elif method == "DELETE":
            response = requests.delete(url, params=params, data=body, json=data, headers=headers,
                                       timeout=timeout, **kwargs)
        else:
            error = "http method error!"
            return None, None, error
    except Exception as e:
        print("method:", method, "url:", url, "headers:", headers, "params:", params, "body:", body,
              "data:", data, "Error:", e)
        return None, None, e
    code = response.status_code
    if code not in (200, 201, 202, 203, 204, 205, 206):
        text = response.text
        request_url = response.request.url
        print("method:", method, "url:", request_url, "headers:", headers, "params:", params, "body:", body,
              "data:", data, "code:", code, "result:", text)
        return code, None, text
    try:
        result = response.json()
    except:
        result = response.text
        print("response data is not json format!")
        print("method:", method, "url:", url, "headers:", headers, "params:", params, "body:", body,
              "data:", data, "code:", code, "result:", json.dumps(result))
    print("method:", method, "url:", url, "headers:", headers, "params:", params, "body:", body,
          "data:", data, "code:", code)
    return code, result, None



def send_order(symbol, amount, order_side, order_type, position_side, price=None,
               client_order_id=None, time_in_force=None, trigger_profit_price=None,
               trigger_stop_price=None):
    """
    :return: send order
    """
    params = {
        "orderSide": order_side,
        "orderType": order_type,
        "origQty": amount,
        "positionSide": position_side,
        "symbol": symbol
    }
    if price:
        params["price"] = price
    if client_order_id:
        params["clientOrderId"] = client_order_id
    if time_in_force:
        params["timeInForce"] = time_in_force
    if trigger_profit_price:
        params["triggerProfitPrice"] = trigger_profit_price
    if trigger_stop_price:
        params["triggerStopPrice"] = trigger_stop_price

    bodymod = "application/json"
    path = "/future/trade" + '/v1/order/create'
    url = "https://fapi.xt.com" + path
    # params = dict(sorted(params.items(), key=lambda e: e[0]))
    header = _create_sign(path=path, bodymod=bodymod,
                               params=params)
    code, success, error = _fetch(method="POST", url=url, headers=header, data=params, timeout=30)
    return code, success, error


# Place a limit order
try:
    result = send_order(
        symbol="ada_usdt",          # Trading pair
        amount=1,                # Order quantity
        order_side="BUY",           # Order side: BUY or SELL
        order_type="LIMIT",         # Order type: LIMIT or MARKET
        position_side="LONG",       # Position side: LONG or SHORT
        price=0.99,                 # Limit price
        client_order_id="myOrder1"  # Optional: Client order ID
    )
    print("Order Result:", result)
except Exception as e:
    print("Error placing order:", e)

