"""msgpackrpc yerine kucuk bir katman: AirSim istemcisi bunu kullanir.

AirSim'in Python paketi eski msgpack-rpc-python'a (tornado < 5) bagli; o surum Python 3.10 ve sonrasinda
calismiyor. AirSim sunucusu duz msgpack-rpc konusur: [0, kimlik, yontem, parametreler] gider,
[1, kimlik, hata, sonuc] gelir. Bu modul o kadarini, tek soket ve kilitle yapar.
"""
import itertools
import socket
import threading

import msgpack


class RPCError(Exception):
    pass


class error:  # noqa: N801 -- msgpackrpc.error.RPCError adiyla erisilir
    RPCError = RPCError
    TimeoutError = TimeoutError
    TransportError = ConnectionError


class Address:
    def __init__(self, host, port):
        self.host, self.port = host, int(port)


def _default(obj):
    if hasattr(obj, 'to_msgpack'):
        return obj.to_msgpack()
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    raise TypeError(f'msgpack: {type(obj)!r} yazilamiyor')


class _Done:
    def __init__(self, result):
        self._result = result

    def join(self):
        return self._result

    def get(self):
        return self._result


class Client:
    def __init__(self, address, timeout=3600, pack_encoding='utf-8', unpack_encoding='utf-8', **_):
        self._sock = socket.create_connection((address.host, address.port), timeout=timeout)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._ids = itertools.count()
        self._unpacker = msgpack.Unpacker(raw=False, strict_map_key=False, max_buffer_size=2 ** 31 - 1)
        self._lock = threading.Lock()

    def call(self, method, *args):
        with self._lock:
            msgid = next(self._ids) & 0x7FFFFFFF
            self._sock.sendall(msgpack.packb([0, msgid, method, list(args)], default=_default, use_bin_type=True))
            while True:
                for msg in self._unpacker:
                    if len(msg) == 4 and msg[0] == 1 and msg[1] == msgid:
                        if msg[2] is not None:
                            raise RPCError(f'{method}: {msg[2]}')
                        return msg[3]
                data = self._sock.recv(1 << 20)
                if not data:
                    raise ConnectionError('AirSim baglantisi kapandi')
                self._unpacker.feed(data)

    def call_async(self, method, *args):
        """AirSim'in ...Async() yontemleri icin: cagri hemen yapilir, .join() sonucu dondurur."""
        return _Done(self.call(method, *args))

    def close(self):
        try:
            self._sock.close()
        except OSError:
            pass
