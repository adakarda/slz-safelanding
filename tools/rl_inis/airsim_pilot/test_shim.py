"""msgpackrpc katmaninin sinamasi: sahte bir msgpack-rpc sunucusuna karsi airsim istemcisi."""
import socket
import threading

import msgpack


def sahte_sunucu(port_q):
    srv = socket.socket()
    srv.bind(('127.0.0.1', 0))
    srv.listen(1)
    port_q.append(srv.getsockname()[1])
    conn, _ = srv.accept()
    up = msgpack.Unpacker(raw=False)
    while True:
        data = conn.recv(65536)
        if not data:
            break
        up.feed(data)
        for _t, mid, method, params in up:
            if method == 'ping':
                res, err = True, None
            elif method == 'simGetVehiclePose':
                res, err = {'position': {'x_val': 1.0, 'y_val': 2.0, 'z_val': -3.0},
                            'orientation': {'w_val': 1.0, 'x_val': 0.0, 'y_val': 0.0, 'z_val': 0.0}}, None
            elif method == 'simSetVehiclePose':
                res, err = None, None
                assert params[0]['position']['z_val'] == -25.0, params
            elif method == 'simGetImages':
                res, err = [{'image_data_uint8': bytes(range(12)), 'width': 2, 'height': 2, 'camera_name': '0'}], None
            else:
                res, err = None, f'bilinmeyen yontem {method}'
            conn.sendall(msgpack.packb([1, mid, err, res], use_bin_type=True))


q = []
threading.Thread(target=sahte_sunucu, args=(q,), daemon=True).start()
while not q:
    pass
import airsim  # noqa: E402

c = airsim.VehicleClient(ip='127.0.0.1', port=q[0])
assert c.ping() is True
p = c.simGetVehiclePose()
assert (p.position.x_val, p.position.z_val) == (1.0, -3.0), p
c.simSetVehiclePose(airsim.Pose(airsim.Vector3r(0, 0, -25.0), airsim.to_quaternion(0, 0, 0)), True)
r = c.simGetImages([airsim.ImageRequest('0', airsim.ImageType.Scene, False, False)])[0]
assert r.width == 2 and len(r.image_data_uint8) == 12
try:
    c.client.call('yok')
    raise AssertionError('hata bekleniyordu')
except Exception as e:  # noqa: BLE001
    assert 'bilinmeyen' in str(e)
print('katman sinamasi gecti: ping, poz oku/yaz, goruntu, hata')
