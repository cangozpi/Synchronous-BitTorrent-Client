import argparse
import bencodepy
import math
import urllib.parse
import hashlib
import requests
import struct
import socket

# Refer to https://wiki.theory.org/BitTorrentSpecification and http://www.kristenwidman.com/blog/71/how-to-write-a-bittorrent-client-part-2/ for the details of the bittorrent protocol.

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('-f', '--file_path', type=str, default='ubuntu-23.04-desktop-amd64.iso.torrent', required=False, help='path of the *.torrent file you want to download')
args = arg_parser.parse_args()


# Read in .torrent file
with open(args.file_path, mode='rb') as f: #TODO: support info in Multiple File Mode (currently on Info in Single file mode is supported)
    metainfo_file = bencodepy.decode(f.read())
    num_pieces = math.ceil(metainfo_file[b'info'][b'length'] / metainfo_file[b'info'][b'piece length'])
    print("Metainfo file keys:", metainfo_file.keys())
    # print(str(metainfo_file[b'announce'], 'UTF-8'))
    # print(str(metainfo_file[b'info'].keys()))
    # print(str(metainfo_file[b'info'][b'length']))
    # print(str(metainfo_file[b'info'][b'name']))
    # print(str(metainfo_file[b'info'][b'piece length']))
    # print(len(metainfo_file[b'info'][b'pieces']))
    print('-'*30)

# --- Tracker:
tracker_url = str(metainfo_file[b'announce'], 'UTF-8')

# Tracker Request Parameters: (urlencoded): (i.e. a '?' after the announce URL, followed by 'param=value' sequences separated by '&')
info_hash = hashlib.sha1(bencodepy.encode(metainfo_file[b"info"])).digest()
assert len(info_hash) == 20, "info_hash should be 20 byte SHA1 hash fo the value of the info key from the Metainfo file."
assert len(metainfo_file[b"info"][b"pieces"]) % 20 == 0, "The length of the string must be a multiple of 20"
info_hash_percent_encoded = urllib.parse.quote(info_hash, safe='') # percent encode binary data in the url (percent-encode) (refer to: https://stackoverflow.com/questions/1695183/how-can-i-percent-encode-url-parameters-in-python)

peer_id = 20 * b'a'
peer_id_percent_encoded = urllib.parse.quote(peer_id, safe='')
assert len(peer_id_percent_encoded) == 20, "peer_id must be 20 bytes long"
port = 6881
uploaded = 0
downloaded = 0
left = metainfo_file[b'info'][b'length']
compact = 1
event = "started"
numwant = 50 # optional

def get_url_param_string(name, value):
    return f'{name}={value}'

info_hash_url_param = get_url_param_string('info_hash', info_hash_percent_encoded)
peer_id_url_param = get_url_param_string('peer_id', peer_id_percent_encoded)
port_url_param = get_url_param_string('port', port)
uploaded_url_param = get_url_param_string('uploaded', uploaded)
downloaded_url_param = get_url_param_string('downloaded', downloaded)
left_url_param = get_url_param_string('left', left)
compact_url_param = get_url_param_string('compact', compact)
event_url_param = get_url_param_string('event', event)
numwant_url_param = get_url_param_string('numwant', numwant)

tracker_request_url_params = [
    info_hash_url_param,
    peer_id_url_param,
    port_url_param,
    uploaded_url_param,
    downloaded_url_param,
    left_url_param,
    compact_url_param,
    event_url_param,
    numwant_url_param
]

def concatenate_url_params(base_url, url_params: list):
    url = base_url + '?'
    for p in url_params:
        if url[-1] != '?':
            url += ("&" + p)
        else:
            url += p
    return url

tracker_request_url = concatenate_url_params(base_url=tracker_url, url_params=tracker_request_url_params)

# Get list of Peers by making a request to the Tracker
r = requests.get(tracker_request_url, 
                headers={'Accept': 'text/plain'})

if r.status_code != 200:
    raise "Tracker Request failed"
else:
    # print(f"Status Code: {r.status_code}")
    # print(f"Content: {bencodepy.decode(r.content)}")
    tracker_response = bencodepy.decode(r.content)
    # TODO: support dictionary model for peers (currently only binary model is supported)
    peers = tracker_response[b'peers']
    addr_bytes, port_bytes = (
                    peers[0:0 + 4], peers[0 + 4:0 + 6]
                )
    peers = [{
        'ip_addr': '.'.join([ str(p) for p in struct.unpack('!4B', peers[i:i+4])]),
        'port': int(''.join( str(p) for p in struct.unpack('!H', peers[i+4:i+6])))
    } for i in range(0, len(peers), 6)]
    # print(peers)
    print('-'*30)


# --- Peer Wire Protocol (TCP):
choked = True
interested = False

# Connect to Peer:
connected_to_a_peer = False
peer_idx = 0
while connected_to_a_peer == False:
    peer = peers[peer_idx]
    try:
        print('Connecting to peer at :', peer['ip_addr'], peer['port'])
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((peer['ip_addr'], peer['port']))
        connected_to_a_peer = True
    except:
        peer_idx += 1
        if peer_idx >= len(peers):
            raise Exception('Could not connect to any of the available peers')



# Handshake:
def get_handshake_msg(info_hash, peer_id):
    pstr = "BitTorrent protocol"
    pstrlen = len(pstr)
    reserved = 00000000

    handshake_msg = struct.pack(f'!b{pstrlen}sq20s20s', pstrlen, pstr.encode(), reserved, info_hash, peer_id)
    return handshake_msg

handshake_msg = get_handshake_msg(info_hash, peer_id)
print('Sending Handshake message')
s.send(handshake_msg)
peer_response = s.recv(2**15) # ignore response to Handshake msg


global have_payloads, have_payloads_idx
have_payloads = []
have_payloads_idx = 0
downloading_a_piece_flag = False
while True:
    peer_response = s.recv(2**15)
    if len(peer_response) == 0:
        continue

    msg_len, msg_id = struct.unpack('!Ib', peer_response[:5])
    print('*'*5)
    print(f'Received Message: (len:{msg_len}, id:{msg_id})')

    if choked or (interested == False):
        # Interested Message:
        def get_interested_msg():
            msg_len = 1
            msg_id = 2
            interested_msg = struct.pack(f'!Ib', msg_len, msg_id)
            return interested_msg

        interested_msg = get_interested_msg()
        print(f'Sending Interested message')
        s.send(interested_msg)
        interested = True


    if msg_id == 1: # Unchoke msg
        print('Received Unchoke message')
        choked = False

    
    if msg_id == 4: # Have msg
        piece_index = struct.unpack('!IbI', peer_response)[2]
        print(f'Received Have message for piece_index: {piece_index}')
        have_payloads.append(int(piece_index))

    if len(have_payloads) != 0 and (choked == False) and (interested) and (downloading_a_piece_flag == False): # Request msg
        # Request Message:
        def get_request_msg():
            global have_payloads
            global have_payloads_idx
            msg_len = 13
            msg_id = 6
            index = have_payloads[have_payloads_idx]
            have_payloads_idx += 1
            begin = 0
            # length = metainfo_file[b'info'][b'piece length']
            length = 2**12 # TODO: handle last requested piece having a smaller length than 2**14
            request_msg = struct.pack(f'!IbIII', msg_len, msg_id, index, begin, length)
            assert interested and (choked == False)
            return request_msg

        request_msg = get_request_msg()
        print('Sending Request message:', struct.unpack('!IbIII', request_msg))
        s.send(request_msg)
        downloading_a_piece_flag = True
    
    if msg_id == 7: # Piece msg
        print(f'Received Piece message')
        X = msg_len - 9
        print(X, msg_len, f'!IbII{X}s', len(peer_response))
        index, begin, block = struct.unpack(f'!IbII{X}s', peer_response)[2:] # TODO:  fix and implement this !
        print(block)
