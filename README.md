# Synchronous BitTorrent Client

This code implements a simple synchronous BitTorrent client which can be used to download content from a given *.torrent file. It is meant to serve as a simple toy implementation of a peer to peer (p2p) protocol.

---
* __To run:__
    1. Download any *.torrent file you want.
    For example
        ```bash
        wget https://releases.ubuntu.com/lunar/ubuntu-23.04-desktop-amd64.iso
        ```
    
    2. Run the code by specifying your *.torrent file as an argument to _--file_path=_
        ```bash
        python3 main.py --file_path=ubuntu-23.04-desktop-amd64.iso.torrent
        ```
        * __Sample Output__:
        ```text
        Metainfo file keys: dict_keys([b'announce', b'announce-list', b'comment', b'created by', b'creation date', b'info'])
        ------------------------------
        ------------------------------
        Connecting to peer at : 185.125.190.59 6950
        Sending Handshake message
        *****
        Received Message: (len:1, id:1)
        Sending Interested message
        Received Unchoke message
        *****
        Received Message: (len:5, id:4)
        Received Have message for piece_index: 12266
        Sending Request message: (13, 6, 12266, 0, 4096)
        *****
        Received Message: (len:4105, id:7)
        Received Piece message
        4096 4105 !IbII4096s 2860
        ```

---

* __Resources on BitTorrent Protocol:__

    Refer to https://wiki.theory.org/BitTorrentSpecification and http://www.kristenwidman.com/blog/71/how-to-write-a-bittorrent-client-part-2/ for the details of the bittorrent protocol.