# Electrum Redd - lightweight Reddcoin client
# Copyright (C) 2014 'laudney@reddcoin'
# Copyright (C) 2014 'gnasher@reddcoin.com'
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
__author__ = 'laudney, gnasher'


from pprint import pprint
import numpy as np


# Kimoto Gravity Well difficulty retarget algo for Reddcoin
class KGW(object):
    def __init__(self):
        self.time_day_seconds = 24 * 60 * 60
        self.last_pow_block = 260799

        # 0x00000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        self.max_target = 2**236 - 1
        self.max_nbits = 0x1e0fffff
        self.min_difficulty = 0xFFFF / (2**28 - 1.0 / 2**208)

        self.genesis_target = 0x00000FFFF0000000000000000000000000000000000000000000000000000000
        self.genesis_nbits = 0x1e0ffff0

        self.posv_reset_target = 2**224 - 1
        self.posv_reset_difficulty = 0xFFFF / (2**16 - 1.0 / 2**208)
        self.posv_reset_nbits = 0x1d00ffff

    def past_blocks(self, next_height):
        if next_height <= 6000:
            past_seconds_min = int(self.time_day_seconds * 0.01)
            past_seconds_max = int(self.time_day_seconds * 0.14)
        else:
            past_seconds_min = self.time_day_seconds / 4
            past_seconds_max = self.time_day_seconds * 7

        past_blocks_min = past_seconds_min / 60
        past_blocks_max = past_seconds_max / 60

        return int(past_blocks_min), int(past_blocks_max)

    def target2nbits(self, target):
        target = int(target)
        MM = 256 * 256 * 256
        c = ("%064X" % target)[2:]
        i = 31
        while c[0:2] == "00":
            c = c[2:]
            i -= 1

        c = int('0x' + c[0:6], 16)
        if c >= 0x800000:
            c /= 256
            i += 1

        return int(c + MM * i)

    def nbits2target(self, nbits):
        nbits = int(nbits)
        MM = 256 * 256 * 256
        a = nbits % MM
        if a < 0x8000:
            a *= 256

        return a * pow(2, 8 * int(nbits / MM - 3))

    def get_target_vanilla(self, chain=None):
        if chain is None or len(chain) == 0:
            return self.genesis_nbits, self.genesis_target

        first_block = chain[0]
        last_block = chain[-1]
        last_timestamp = int(last_block.get('timestamp'))
        first_height = max(0, first_block.get('block_height') - 1)
        last_height = last_block.get('block_height')
        next_height = last_height + 1

        past_blocks_min, past_blocks_max = self.past_blocks(next_height)

        is_posv = last_height >= self.last_pow_block

        if is_posv:
            first_height = self.last_pow_block

        if last_height < past_blocks_min:
            return self.max_nbits, self.max_target

        if is_posv and (last_height - self.last_pow_block) < past_blocks_min:
            return self.posv_reset_nbits, self.posv_reset_target

        past_blocks_mass = past_rate_actual_seconds = past_rate_target_seconds = 0
        past_target_average = past_target_average_prev = None
        height_reading = last_height

        i = 1
        while height_reading > first_height:
            if i > past_blocks_max:
                break

            past_blocks_mass += 1
            block_reading = chain[-i]
            timestamp_reading = int(block_reading.get('timestamp'))
            target_reading = self.nbits2target(block_reading.get('bits'))

            if i == 1:
                past_target_average = float(target_reading)
            else:
                past_target_average = (target_reading - past_target_average_prev) / float(i) + past_target_average_prev

            past_target_average_prev = past_target_average

            past_rate_actual_seconds = max(0, last_timestamp - timestamp_reading)
            past_rate_target_seconds = 60 * past_blocks_mass
            past_rate_adjustment_ratio = 1.0
            if past_rate_actual_seconds != 0 and past_rate_target_seconds != 0:
                past_rate_adjustment_ratio = float(past_rate_target_seconds) / float(past_rate_actual_seconds)

            event_horizon_deviation = 1 + (0.7084 * pow(past_blocks_mass / 144.0, -1.228))
            event_horizon_deviation_fast = event_horizon_deviation
            event_horizon_deviation_slow = 1 / event_horizon_deviation

            if past_blocks_mass >= past_blocks_min:
                if past_rate_adjustment_ratio <= event_horizon_deviation_slow or \
                        past_rate_adjustment_ratio >= event_horizon_deviation_fast:
                    break

            height_reading -= 1
            i += 1

        # failed to calculate difficulty due to not enough blocks
        if height_reading <= first_height:
            return None, None

        new_target = past_target_average
        if past_rate_actual_seconds != 0 and past_rate_target_seconds != 0:
            new_target *= past_rate_actual_seconds
            new_target /= past_rate_target_seconds

        new_target = min(self.max_target, int(new_target))
        new_nbits = self.target2nbits(new_target)

        return new_nbits, new_target

    def get_target(self, chain=None):
        if chain is None or len(chain) == 0:
            return self.genesis_nbits, self.genesis_target

        last_block = chain[-1]
        last_height = last_block.get('block_height')
        next_height = last_height + 1

        past_blocks_min, past_blocks_max = self.past_blocks(next_height)

        if last_height < past_blocks_min:
            return self.max_nbits, self.max_target

        # PoSV diff reset
        if 0 <= (last_height - self.last_pow_block) < past_blocks_min:
            return self.posv_reset_nbits, self.posv_reset_target

        first_block = chain[0]
        first_height = first_block.get('block_height')

        # truncate from the first PoSV block
        if first_height <= self.last_pow_block < last_height:
            chain = chain[(self.last_pow_block - first_height + 1):]

        # too many blocks provided?
        if len(chain) > past_blocks_max:
            chain = chain[-int(past_blocks_max):]

        blocks_mass_range = np.arange(1, len(chain)+1)
        event_horizon_fast = 1 + (0.7084 * np.power(blocks_mass_range / 144.0, -1.228))
        event_horizon_slow = 1.0 / event_horizon_fast

        chain_target = np.array(list(map(self.nbits2target, [c.get('bits') for c in chain])), dtype=np.object)
        chain_gap = np.insert(np.diff(np.array([c.get('timestamp') for c in chain])), 0, 0)

        past_rate_actual_gaps = np.roll(chain_gap[::-1], 1)
        past_rate_actual_gaps[0] = 0
        past_rate_actual_seconds = np.maximum(0.0, np.cumsum(past_rate_actual_gaps))
        past_rate_target_seconds = 60 * blocks_mass_range
        past_rate_adjustment_ratio = past_rate_target_seconds / past_rate_actual_seconds
        past_rate_adjustment_ratio[0] = 1.0

        ratio = past_rate_adjustment_ratio[int(past_blocks_min-1):]
        slow = event_horizon_slow[int(past_blocks_min-1):int(past_blocks_min+len(ratio)-1)]
        fast = event_horizon_fast[int(past_blocks_min-1):int(past_blocks_min+len(ratio)-1)]

        adjustment_indices = np.logical_or(ratio <= slow, ratio >= fast)
        if np.any(adjustment_indices):
            adjustment_index = np.arange(len(adjustment_indices))[adjustment_indices][0]
        else:
            adjustment_index = len(ratio) - 1

        adjustment_ratio = ratio[adjustment_index]

        past_target_average = np.mean(chain_target[-int(adjustment_index+past_blocks_min):])
        new_target = min(self.max_target, int(past_target_average / adjustment_ratio))
        new_nbits = self.target2nbits(new_target)

        return new_nbits, new_target

    def get_chain_target(self, prev_chain, chain):
        full_chain = prev_chain + chain
        full_target = np.array(list(map(self.nbits2target, [c.get('bits') for c in full_chain])), dtype=np.object)
        full_gap = np.insert(np.diff(np.array([c.get('timestamp') for c in full_chain])), 0, 0)

        first_height = full_chain[0].get('block_height')

        # calculation that can be done just once
        blocks_mass_range = np.arange(1, len(full_chain)+1)
        event_horizon_fast = 1 + (0.7084 * np.power(blocks_mass_range / 144.0, -1.228))
        event_horizon_slow = 1.0 / event_horizon_fast

        # next_height specific
        results = []
        for next_height in [c.get('block_height') for c in chain]:
            if next_height == 0:
                results.append((self.genesis_nbits, self.genesis_target))
                continue

            last_height = next_height - 1
            past_blocks_min, past_blocks_max = self.past_blocks(next_height)

            if last_height < past_blocks_min:
                results.append((self.max_nbits, self.max_target))
                continue

            # PoSV diff reset
            if 0 <= (last_height - self.last_pow_block) < past_blocks_min:
                results.append((self.posv_reset_nbits, self.posv_reset_target))
                continue

            if first_height <= self.last_pow_block < last_height:
                # # truncate from the first PoSV block
                past_blocks_index = np.arange(next_height - past_blocks_max, next_height, dtype=np.int64) - self.last_pow_block - 1
            else:
                past_blocks_index = np.arange(next_height - past_blocks_max, next_height, dtype=np.int64) - first_height

            past_blocks_index = past_blocks_index[past_blocks_index >= 0]
            past_blocks_mass_range = np.arange(1, len(past_blocks_index)+1)
            chain_target = full_target[past_blocks_index]
            chain_gap = full_gap[past_blocks_index]

            # Below are indexed by past_blocks_mass_range
            past_rate_actual_gaps = np.roll(chain_gap[::-1], 1)
            past_rate_actual_gaps[0] = 0

            past_rate_actual_seconds = np.maximum(0.0, np.cumsum(past_rate_actual_gaps))
            past_rate_target_seconds = 60 * past_blocks_mass_range
            zero_idx = (past_rate_actual_seconds == 0)
            past_rate_actual_seconds[zero_idx] = past_rate_target_seconds[zero_idx]
            past_rate_adjustment_ratio = past_rate_target_seconds / past_rate_actual_seconds
            past_rate_adjustment_ratio[0] = 1.0

            ratio = past_rate_adjustment_ratio[int((past_blocks_min-1)):]
            slow = event_horizon_slow[int(past_blocks_min-1):int(past_blocks_min+len(ratio)-1)]
            fast = event_horizon_fast[int(past_blocks_min-1):int(past_blocks_min+len(ratio)-1)]

            adjustment_indices = np.logical_or(ratio <= slow, ratio >= fast)
            if np.any(adjustment_indices):
                adjustment_index = np.arange(len(adjustment_indices))[adjustment_indices][0]
            else:
                adjustment_index = len(ratio) - 1

            adjustment_ratio = ratio[adjustment_index]

            past_target_average = np.mean(chain_target[-int(adjustment_index+past_blocks_min):])
            new_target = min(self.max_target, int(past_target_average / adjustment_ratio))
            new_nbits = self.target2nbits(new_target)
            results.append((new_nbits, new_target))

        return results
