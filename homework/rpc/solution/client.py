#!/usr/bin/env python3

import argparse
import logging

from dslib import Communicator, Message

from common import Store


class StoreProxy(Store):
    """This is client-side proxy for Store service"""

    def __init__(self, server_addr):
        self._client = RpcClient(server_addr)

    def put(self, key, value, overwrite):
        return self._client.call('put', key, value, overwrite)

    def get(self, key):
        return self._client.call('get', key)

    def append(self, key, value):
        return self._client.call('append', key, value)

    def remove(self, key):
        return self._client.call('remove', key)


class RpcClient:
    """This is client-side RPC implementation"""

    def __init__(self, server_addr):
        self._comm = Communicator('client')
        # Your implementation
        self.server_addr = server_addr
        pass

    def call(self, func, *args):
        """Call function on RPC server and return result"""

        # Your implementation
        import random
        unique_id = random.random()
        if func in ['get', 'put']:  # idempotent
            while True:
                self._comm.send(Message(message_type=func, body=args, headers=unique_id, sender=self._comm.addr),
                                self.server_addr)
                ans = self._comm.recv(0.5)
                if ans:
                    if ans._type == 'ERROR':
                        raise RuntimeError(ans._body)
                    return ans._body
        else:
            self._comm.send(Message(message_type=func, body=args, headers=unique_id, sender=self._comm.addr),
                            self.server_addr)
            ans = self._comm.recv(0.5)
            if ans:
                if ans._type == 'ERROR':
                    raise RuntimeError(ans._body)
                return ans._body
            else:
                raise RuntimeError('Response timeout')


class User:
    """This class mocks a user during tests by invoking proxy functions"""

    def __init__(self, proxy):
        self._proxy = proxy
        # reuse communicator from proxy
        self._comm = proxy._client._comm

    def run(self):
        while True:
            msg = self._comm.recv()

            # Calls are passed as "CALL func arg1 arg2 ..."
            if msg.type == 'CALL' and msg.is_local():
                params = msg.body.split(' ')
                func = params[0]
                args = map(self._parse_arg, params[1:])

                try:
                    if func == 'get':
                        result = self._proxy.get(*args)
                    elif func == 'put':
                        result = self._proxy.put(*args)
                    elif func == 'append':
                        result = self._proxy.append(*args)
                    elif func == 'remove':
                        result = self._proxy.remove(*args)
                    resp = Message('RESULT', result)
                    self._comm.send_local(resp)
                except Exception as err:
                    resp = Message('ERROR', str(err))
                    self._comm.send_local(resp)

    def _parse_arg(self, arg):
        if arg == 'True':
            return True
        elif arg == 'False':
            return False
        else:
            return arg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', dest='server_addr', metavar='host:port',
                        help='server address', default='127.0.0.1:9701')
    parser.add_argument('-d', dest='log_level', action='store_const', const=logging.DEBUG,
                        help='print debugging info', default=logging.WARNING)
    args = parser.parse_args()
    logging.basicConfig(format="%(asctime)s - %(message)s", level=args.log_level)

    store = StoreProxy(args.server_addr)
    user = User(store)
    user.run()


if __name__ == "__main__":
    main()
