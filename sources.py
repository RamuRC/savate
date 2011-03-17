# -*- coding: utf-8 -*-

import helpers
import looping
import collections
import math

class StreamSource(looping.BaseIOEventHandler):

    def __init__(self, server, sock, address, content_type, request_parser):
        self.server = server
        self.sock = sock
        self.address = address
        self.content_type = content_type
        self.request_parser = request_parser
        self.path = self.request_parser.request_path

    def handle_event(self, eventmask):
        if eventmask & looping.POLLIN:
            while True:
                packet = helpers.handle_eagain(self.sock.recv, self.RECV_BUFFER_SIZE)
                if packet == None:
                    # EAGAIN
                    break
                elif packet == b'':
                    # End of stream
                    print 'End of stream for %s, %s' % (self.sock, self.address)
                    self.server.remove_source(self)
                    # FIXME: publish "EOS" packet
                    break
                else:
                    self.publish_packet(packet)
        else:
            print 'Unexpected eventmask %s' % (eventmask)

    def publish_packet(self, packet):
        self.server.publish_packet(self, packet)

    def new_client(self, client):
        # Do nothing by default
        pass

class BufferedRawSource(StreamSource):

    # Incoming maximum buffer size
    RECV_BUFFER_SIZE = 64 * 2**10

    # Temporary buffer size
    TEMP_BUFFER_SIZE = 4 * 2**10

    # Size of initial data burst for clients
    BURST_SIZE = 32 * 2**10

    def __init__(self, server, sock, address, content_type, request_parser):
        StreamSource.__init__(self, server, sock, address, content_type, request_parser)
        self.buffer_data = request_parser.body
        self.burst_packets = collections.deque([self.buffer_data], math.ceil(float(self.BURST_SIZE) / float(self.TEMP_BUFFER_SIZE)))

    def publish_packet(self, packet):
        self.buffer_data = self.buffer_data + packet
        if len(self.buffer_data) >= self.TEMP_BUFFER_SIZE:
            StreamSource.publish_packet(self, self.buffer_data)
            self.burst_packets.append(self.buffer_data)
            self.buffer_data = ''

    def new_client(self, client):
        for packet in self.burst_packets:
            client.add_packet(packet)

class FLVSource(StreamSource):

    def __init__(self, sock, server, address, request_parser):
        StreamSource.__init__(self, sock, server, address, request_parser)
        self.stream_header = None
        self.initial_tags = []
        self.current_output_buffer = None

    # def handle_event(self, eventmask):
    #     if eventmask & looping.POLLIN:
    #         if self.stream_header


sources_mapping = {
    b'video/x-flv': FLVSource,
    b'audio/x-hx-aac-adts': BufferedRawSource,
    b'application/octet-stream': BufferedRawSource,
    }
