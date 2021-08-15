"""
Implementation of UUID v6 per the April 2021 draft update to RFC4122 from 2005:
<https://datatracker.ietf.org/doc/html/draft-peabody-dispatch-new-uuid-format>.

This code is a simplication of the Python version in
<https://github.com/uuid6/prototypes/blob/main/python/new_uuid.py>.

Stephen Simmons, 2021-08-15
"""

import datetime
import random
import time
from typing import Literal, Optional, Union
import uuid

_last_uuid_v6_time = 0
_last_uuid_v6_seq = 0


def uuid6(fmt: Literal['hex', 'int', 'uuid', 'str'] = 'str',
          as_of: Union[None, datetime.datetime, float] = None,
          seed: Optional[int] = None,
          seq: Optional[int] = None) -> Union[str, int, uuid.UUID]:
    """
    Construct a RFC8122 UUIDv6, returned as str, int, hex or a UUID object.
    
    The UUIDs contain 60 timestamp bits (resolution of 200ns), 48 random bits,
    and a sequence counter (14 bits) if two consecutive calls have the same timestamp.
    The resulting hex/str UUIDs are time-sortable so that recently-created UUIDs
    are close together while still highly unlikely to collide.
    
    Optional parameter `as_of` may specify a different time, as a float 
    timestamp or datetime object). Otherwise the current time is used.
    
    The random seed and random/sequential seq values may also be overridden
    in order to produce fully deterministic output.
    
    uuid6(fmt='int')  -> 40873015229028996969259476966618100869
    uuid6(fmt='hex')  -> '1ebfdb3caed56f388001dd94caaef485'
    uuid6(fmt='str')  -> '1ebfdb3c-aed5-6f38-8001-dd94caaef485'
    uuid6(fmt='uuid') -> UUID('1ebfdb3c-aed5-6f38-8001-dd94caaef485')
    """
    # Format of 128 bits are:
    # time_high[32]|time_mid[16]|version[4]|time_low[12]|variant[2]|clock_seq_high[6]|clock_seq_low[8]|node[48]
    global _last_uuid_v6_time, _last_uuid_v6_seq

    uuid_version = 6
    uuid_variant = 2

    if as_of is None:
        ts_ns = time.time_ns()
    elif isinstance(as_of, datetime.datetime):
        ts_ns = int(as_of.replace(tzinfo=datetime.timezone.utc).timestamp() * 1_000_000_000)
    elif isinstance(as_of, float):
        ts_ns = int(as_of * 1_000_000_000)
    else:
        raise ValueError(f"Unexpected value for as_of: {as_of}")
    time_val = (ts_ns // 100) + 0x01b21dd213814000
    
    if seq is not None:
        _last_uuid_v6_seq = seq
    elif _last_uuid_v6_seq is None:
        _last_uuid_v6_seq = random.getrandbits(14)
    elif time_val <= _last_uuid_v6_time:
        _last_uuid_v6_seq += 1
    
    _last_uuid_v6_time = time_val
    
    node = random.getrandbits(48) if seed is None else (seed & ((1 << 48) - 1))

    # Build final 128-bit number
    val = (time_val >> 12) # Top 48 bits
    val = (val << 4) + uuid_version # Top 52 bits
    val = (val << 12) + (time_val & 4095) # Top 64 bits. Here 4095 = 1 << 12 - 1.
    val = (val << 2) + uuid_variant # Top 66 bits
    val = (val << 14) + (_last_uuid_v6_seq & 16383) # Top 80 bits
    int_val = (val << 48) + node # Final number
    
    # Return in the desired format
    if fmt == 'uuid':
        return uuid.UUID(int=int_val)
    elif fmt == 'int':
        return int_val

    hex_val = f"{int_val:032x}"
    if fmt == 'hex':
        return hex_val
    else: # fmt == 'str'
        return "-".join([hex_val[:8], hex_val[8:12], hex_val[12:16], hex_val[16:20], hex_val[20:]])


def uuid6_to_datetime(s: Union[str, uuid.UUID, int],
        suppress_uuid_version_error=True) -> datetime.datetime:
    """
    Recover the timestamp from a UUIDv6, passed in
    as a string, integer or a UUID object.
    
    If the UUID is not a version 6 UUID, either raise a ValueError
    or return None, depending on suppress_uuid_version_error.
    
    Usage:
    >>> uuid6_to_datetime("1eb22fe4-3f0c-62b1-a88c-8dc55231702f")
    datetime.datetime(2020, 11, 10, 2, 41, 42, 182162)
    """
    if isinstance(s, uuid.UUID):
        x = s.int
    elif isinstance(s, str):
        x = int(s.replace('-', ''), base=16)
    else:
        x = s

    uuid_version =  (x >> 76) & 15
    if uuid_version != 6:
        if suppress_uuid_version_error:
            return None
        else:
            raise ValueError(f"{str(s)} is a version {uuid_version} UUID, not v6, so we cannot extract the timestamp.")
    
    time_val = ((x >> 80) << 12) + ((x >> 64) & 4095)
    timestamp_ns = (time_val - 0x01b21dd213814000) * 100.0
    timestamp = timestamp_ns / 1000000000.0
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)


def test_uuid6():
    # Note the sequence value increments by 1 between each of these uuid6(...) calls
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    seed = random.getrandbits(48)
    seq = random.getrandbits(14)
    
    out1 = uuid6('int', now, seed, seq)
    out2 = uuid6('hex', now, seed, seq)
    out3 = uuid6('str', now, seed, seq)
    out4 = uuid6('uuid', now, seed, seq) 

    #print(out1)
    #print(out2)
    #print(out3)
    #print(str(out4))
    
    assert out4.int == out1
    assert out4.hex == out2
    assert str(out4) == out3
    
    #print(now)
    #print(uuid6_to_datetime(out4))
    assert uuid6_to_datetime(out4) == now # Should be equal to microseconds resolution
    
if __name__ == '__main__':
    test_uuid6()
