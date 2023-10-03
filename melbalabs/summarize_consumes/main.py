import argparse
import collections
import datetime
import io
import re
import sys
import webbrowser
import zipfile
from datetime import datetime as dt


import requests



rename_consumable = {
    'Supreme Power': 'Flask of Supreme Power',
    'Distilled Wisdom': 'Flask of Distilled Wisdom',
    'Rage of Ages': 'Rage of Ages (ROIDS)',
    'Health II': 'Elixir of Fortitude',
    'Fury of the Bogling': 'Bogling Root',
    'Elixir of the Sages': '??? Elixir of the Sages ???',
    'Shadow Power': 'Elixir of Shadow Power',
    'Greater Firepower': 'Elixir of Greater Firepower',
    'Fire Power': 'Elixir of Firepower',
    'Greater Agility': 'Elixir of Greater Agility',
    'Spirit of the Boar': 'Lung Juice Cocktail',
    'Greater Armor': 'Elixir of Superior Defense',
    'Mana Regeneration': 'Mana Regeneration (food or mageblood)',
    'Free Action': 'Free Action Potion',
    'Frost Power': 'Elixir of Frost Power',
    'Nature Protection ': 'Nature Protection',
    'Shadow Protection ': 'Shadow Protection',
    '100 energy': 'Thistle Tea',
    'Sharpen Weapon - Critical': 'Elemental Sharpening Stone',
    'Consecrated Weapon': 'Consecrated Sharpening Stone',
    'Sharpen Blade V': 'Dense Sharpening Stone',
    'Enhance Blunt Weapon V': 'Dense Weighstone',
    'Cure Ailments': 'Jungle Remedy',
    'Stoneshield': '??? Lesser Stoneshield Potion ???',
    'Restoration': 'Restorative Potion',
    'Enlarge': 'Elixir of Giant Growth',
    'Greater Intellect': 'Elixir of Greater Intellect',
    'Infallible Mind': 'Infallible Mind (Cerebral Cortex Compound)',
    'Crystal Protection': 'Crystal Protection (Crystal Basilisk Spine)',
}


def deaths_log(line):
    if not 'dies.' in line:
        return

    needle = r'  ([\w ]+) dies\.'
    match = re.search(needle, line)
    if match:
        name = match.group(1)
        death_count[name] += 1
        return True


def consolidated_log(line):
    idx = line.find("CONSOLIDATED: ")
    if idx == -1:
        return


    line = line[idx+len('CONSOLIDATED: '):]
    entries = line.split('{')
    for entry in entries:
        needle = r'PET: \d+\.\d+\.\d+ \d+:\d+:\d+&(\w+)&(\w+)'
        match = re.search(needle, line)
        if match:
            player = match.group(1)
            pet = match.group(2)
            pet_detect[pet] = player
            player_detect[player] = 'pet: ' + pet
    return True

def healpot_lookup(amount):
    # bigger ranges for rounding errors
    if 1049 <= amount <= 1751:
        return 'Healing Potion - Major'
    if 699 <= amount <= 901:
        return 'Healing Potion - Superior'
    if 454 <= amount <= 586:
        return 'Healing Potion - Greater'
    if 139 <= amount <= 181:
        return 'Healing Potion - Lesser'
    if 69 <= amount <= 91:
        return 'Healing Potion - Minor'
    return 'Healing Potion - unknown'


def health_potion(line):
    needle = r'Healing Potion heals (\w+) for (\d+)'
    match = re.search(needle, line)
    if match:
        name = match.group(1)
        amount = int(match.group(2))
        consumable = healpot_lookup(amount)
        player[name][consumable] += 1
        return True

    needle = r'Healing Potion critically heals (\w+) for (\d+)'
    match = re.search(needle, line)
    if match:
        name = match.group(1)
        amount = int(match.group(2))
        consumable = healpot_lookup(amount/1.5)
        player[name][consumable] += 1
        return True

def mana_potion(line):
    needle = r'(\w+) gains (\d+) Mana from .* Restore Mana'
    match = re.search(needle, line)
    if match:
        name = match.group(1)
        mana = int(match.group(2))
        consumable = 'Restore Mana (mana potion?)'
        if 1350 <= mana <= 2250:
            consumable = 'Mana Potion - Major'
        elif 900 <= mana <= 1500:
            consumable = 'Mana Potion - Superior'
        elif 700 <= mana <= 900:
            consumable = 'Mana Potion - Greater'
        elif 455 <= mana <= 585:
            consumable = 'Mana Potion - 455 to 585'
        elif 280 <= mana <= 360:
            consumable = 'Mana Potion - Lesser'
        elif 140 <= mana <= 180:
            consumable = 'Mana Potion - Minor'
        player[name][consumable] += 1
        return True

def mana_rune(line):
    for consumable in ['Dark Rune', 'Demonic Rune']:
        needle = r'(\w+) gains (\d+) Mana from .* ' + consumable
        match = re.search(needle, line)
        if match:
            name = match.group(1)
            player[name][consumable] += 1
            return True



def great_rage(line):
    for consumable in ['Mighty Rage', 'Great Rage', 'Rage']:
        needle = r'(\w+) gains \d+ Rage from .* ' + consumable
        match = re.search(needle, line)
        if match:
            name = match.group(1)
            consumable += ' Potion'
            player[name][consumable] += 1
            return True


def tea_with_sugar(line):
    match = re.search(r'Tea with Sugar.*heals (\w+)', line)
    if match:
        name = match.group(1)
        player[name]['Tea with Sugar'] += 1
        return True

def gains_consumable(line):
    for consumable in [
            'Greater Arcane Elixir',
            'Arcane Elixir',
            'Elixir of the Mongoose',
            'Elixir of the Giants',
            'Flask of the Titans',
            'Supreme Power',
            'Distilled Wisdom',
            'Spirit of Zanza',
            'Swiftness of Zanza',
            'Sheen of Zanza',
            'Rage of Ages',
            'Invulnerability',
            'Noggenfogger Elixir',
            'Shadow Power',
            'Greater Stoneshield',
            'Stoneshield',
            'Health II',
            'Rumsey Rum Black Label',
            'Rumsey Rum',
            'Fury of the Bogling',
            'Winterfall Firewater',
            'Greater Agility',
            'Elixir of the Sages',
            'Greater Firepower',
            'Fire Power',
            'Strike of the Scorpok',
            'Spirit of the Boar',
            'Greater Armor',
            'Free Action',
            'Blessed Sunfruit',
            'Elixir of Resistance',
            'Gordok Green Grog',
            'Frost Power',
            'Gift of Arthas',
            '100 Energy',  # Restore Energy aka Thistle Tea
            'Restoration',
            'Crystal Ward',
            'Infallible Mind',
            'Crystal Protection',


            # ambiguous
            'Increased Stamina',
            'Increased Intellect',
            'Mana Regeneration',
            'Regeneration',
            'Agility',  # pots or scrolls
            'Strength',
            'Stamina',
            'Enlarge',
            'Greater Intellect',
            # 'Armor',

            'Nature Protection ',  # extra space
            'Shadow Protection ',
            'Fire Protection',
            'Frost Protection',
            'Arcane Protection',
        ]:
            needle = r'(\w+) gains ' + consumable + r' \(1\)'
            match = re.search(needle, line)
            if match:
                name = match.group(1)
                if consumable in rename_consumable:
                    consumable = rename_consumable[consumable]
                player[name][consumable] += 1
                return True

def casts_consumable(line):
    casts_consumables = [
        'Powerful Anti-Venom',
        'Strong Anti-Venom',
        'Cure Ailments',
        'Advanced Target Dummy',
    ]
    for consumable in casts_consumables:
        needle = r'(\w+) casts ' + consumable
        match = re.search(needle, line)
        if match:
            name = match.group(1)
            if consumable in rename_consumable:
                consumable = rename_consumable[consumable]
            player[name][consumable] += 1
            return True



def begins_to_cast_consumable(line):
    begins_to_cast_consumables = [
        'Brilliant Mana Oil',
        'Lesser Mana Oil',
        'Brilliant Wizard Oil',
        'Blessed Wizard Oil',
        'Wizard Oil',
        'Frost Oil',
        'Shadow Oil',
        'Dense Dynamite',
        'Solid Dynamite',
        'Sharpen Weapon - Critical',
        'Consecrated Weapon',
        'Iron Grenade',
        'Thorium Grenade',
        "Kreeg's Stout Beatdown",
        'Fire-toasted Bun',
        'Sharpen Blade V',
        'Enhance Blunt Weapon V',
        'Crystal Force',
    ]

    for consumable in begins_to_cast_consumables:
        needle = r'(\w+) begins to cast ' + consumable
        match = re.search(needle, line)
        if match:
            name = match.group(1)
            if consumable in rename_consumable:
                consumable = rename_consumable[consumable]
            player[name][consumable] += 1
            return 1

def hits_consumable(line):

    hits_consumables = [
        ('Dragonbreath Chili', 10 * 60),
        ('Goblin Sapper Charge', 5 * 60),
    ]
    for consumable, cooldown in hits_consumables:
        needle = r"(\d+)/(\d+) (\d+):(\d+):(\d+).(\d+)  (\w+) 's " + consumable + ' '
        match = re.search(needle, line)
        if match:
            groups = match.groups()
            month, day, hour, minute, sec, ms = int(groups[0]), int(groups[1]), int(groups[2]), int(groups[3]), int(groups[4]), int(groups[5])
            name = groups[-1]
            timestamp = dt(year=current_year, month=month, day=day, hour=hour, minute=minute, second=sec, tzinfo=datetime.timezone.utc)
            unixtime = timestamp.timestamp()  # seconds
            delta = unixtime - last_hit_cache[name][consumable]
            if delta >= cooldown:
                player[name][consumable] += 1
                last_hit_cache[name][consumable] = unixtime
            elif delta < 0:
                # probably a new year, will ignore for now
                raise RuntimeError('fixme')

            return True



def player_detected(line):
    for buff in [
        'Greater Blessing of Wisdom',
        'Greater Blessing of Salvation',
        'Greater Blessing of Light',
        'Greater Blessing of Kings',
        'Greater Blessing of Might',
        'Prayer of Spirit',
        'Prayer of Fortitude',
    ]:
        needle = r'(\w+) gains ' + buff + r' \(1\)'
        match = re.search(needle, line)
        if match:
            name = match.group(1)
            player_detect[name] = buff
            return True


class Huhuran:
    def __init__(self):
        self.log = []
        self.found_huhuran = 0

    def print(self, output):
        if not self.found_huhuran: return
        if not self.log: return

        print("\n\nPrincess Huhuran Log", file=output)
        for line in self.log:
            print('  ', line, end='', file=output)

    def parse(self, line):
        if 'Death by Peasant' in line:
            self.log.append(line)
            return 1
        if 'Princess Huhuran dies' in line:
            self.log.append(line)
            self.found_huhuran = 1
            return 1
        if 'Princess Huhuran gains Frenzy' in line:
            self.log.append(line)
            self.found_huhuran = 1
            return 1
        if "Princess Huhuran 's Frenzy is removed." in line:
            self.log.append(line)
            self.found_huhuran = 1
            return 1
        if 'casts Tranquilizing Shot on Princess Huhuran' in line:
            self.log.append(line)
            self.found_huhuran = 1
            return 1
        if 'Princess Huhuran gains Berserk (1).' in line:
            self.log.append(line)
            self.found_huhuran = 1
            return 1
        if not self.found_huhuran and 'Princess Huhuran' in line:
            self.found_huhuran = 1
            return 1

class Gluth:
    def __init__(self):
        self.log = []
        self.boss_found = 0

    def print(self, output):
        if not self.boss_found: return
        if not self.log: return

        print("\n\nGluth Log", file=output)
        for line in self.log:
            print('  ', line, end='', file=output)

    def parse(self, line):
        """
9/21 22:59:43.807  Jaekta is afflicted by Mortal Wound (2).
9/21 22:59:53.950  Jaekta is afflicted by Mortal Wound (3).
9/21 23:00:03.947  Jaekta is afflicted by Mortal Wound (4).
9/21 23:00:13.870  Jaekta is afflicted by Mortal Wound (5).
9/21 23:00:24.074  Jaekta is afflicted by Mortal Wound (6).
9/21 23:00:34.043  Jaekta is afflicted by Mortal Wound (7).

9/21 22:59:44.495  Gluth 's Decimate hits Mikkasa for 5266.
9/21 22:59:44.495  Gluth 's Decimate hits Psykhe for 6887.
9/21 22:59:44.495  Gluth 's Decimate hits Shumy for 5358.

9/21 22:59:52.517  Hrin casts Tranquilizing Shot on Gluth.
9/21 23:00:03.082  Smahingbolt casts Tranquilizing Shot on Gluth.
9/21 23:00:03.673  Berserkss casts Tranquilizing Shot on Gluth.
9/21 23:00:12.698  Hrin casts Tranquilizing Shot on Gluth.
9/21 23:00:22.440  Yis casts Tranquilizing Shot on Gluth.

9/21 22:58:39.978  Gluth gains Frenzy (1).

9/21 23:00:42.334  Gluth 's Frenzy is removed.

        """
        log_needles = [
            'Gluth dies',
            'Gluth gains Frenzy',
            "Gluth 's Frenzy is removed.",
            'casts Tranquilizing Shot on Gluth',
            "Gluth 's Decimate hits",
        ]
        for needle in log_needles:
            if needle in line:
                self.log.append(line)
                self.boss_found = 1
                return 1
        if not self.boss_found and 'Gluth' in line:
            self.boss_found = 1
            return 1




class BeamChain:
    def __init__(self, logname, beamname, chainsize):
        self.log = []
        self.last_ts = 0
        self.logname = logname
        self.beamname = beamname
        self.chainsize = chainsize  # report chains bigger than this

    def print(self, output):
        if not self.log: return

        print(f"\n\n{self.logname}", file=output)

        batch = []
        for line in self.log:
            if line == '\n':
                if len(batch) > self.chainsize:
                    for batch_line in batch:
                        print('  ', batch_line, end='', file=output)
                batch = []
                batch.append(line)
            else:
                batch.append(line)

        if len(batch) > self.chainsize:
            for batch_line in batch:
                print('  ', batch_line, end='', file=output)



    def parse(self, line):
        """
9/8 23:23:30.876  Eye of C'Thun begins to cast Eye Beam.
9/8 23:23:32.892  Eye of C'Thun 's Eye Beam hits Killanime for 2918 Nature damage.
9/8 23:21:11.776  Eye of C'Thun 's Eye Beam is absorbed by Shendelzare.
9/8 23:07:23.048  Eye of C'Thun 's Eye Beam was resisted by Getterfour.

9/20 23:06:17.787  Sir Zeliek 's Holy Wrath hits Obbi for 477 Holy damage.
9/20 22:51:04.622  Sir Zeliek 's Holy Wrath is absorbed by Exeggute.
9/20 22:38:44.757  Sir Zeliek 's Holy Wrath was resisted by Charmia.
        """
        beamname = self.beamname
        if beamname in line:
            needle = rf"(\d+)/(\d+) (\d+):(\d+):(\d+).(\d+)  {beamname} "
            match = re.search(needle, line)
            cooldown = 2
            if match:
                groups = match.groups()
                month, day, hour, minute, sec, ms = int(groups[0]), int(groups[1]), int(groups[2]), int(groups[3]), int(groups[4]), int(groups[5])
                timestamp = dt(year=current_year, month=month, day=day, hour=hour, minute=minute, second=sec, tzinfo=datetime.timezone.utc)
                unixtime = timestamp.timestamp()
                delta = unixtime - self.last_ts
                if delta >= cooldown:
                    self.log.append('\n')
                    self.last_ts = unixtime
                self.log.append(line)
                return 1


class LogParser:
    # simple parser for individual lines with no context

    def __init__(self, logname, needles):
        self.log = []
        self.logname = logname
        self.needles = needles

    def parse(self, line):
        for needle in self.needles:
            match = re.search(needle, line)
            if match:
                self.log.append(line)
                return 1

    def print(self, output):
        if not self.log: return

        print(f"\n\n{self.logname}", file=output)
        for line in self.log:
            print('  ', line, end='', file=output)




class KTShadowFissure:
    """
    9/28 22:51:03.811  Kel'Thuzad casts Shadow Fissure.
    9/28 22:51:06.876  Shadow Fissure 's Void Blast hits Getterfour for 72890 Shadow damage.
    9/28 22:51:20.183  Kel'Thuzad casts Shadow Fissure.
    9/28 22:51:23.087  Shadow Fissure 's Void Blast hits Sunor for 89663 Shadow damage.
    9/28 22:51:50.105  Kel'Thuzad casts Shadow Fissure.
    9/28 22:51:53.197  Shadow Fissure 's Void Blast hits Lyahsunsworn for 73590 Shadow damage. (24529 resisted)
    """
    def __init__(self):
        logname = 'KT Shadow Fissure Log'
        needles = [
            "Kel'Thuzad casts Shadow Fissure.",
            "Shadow Fissure 's Void Blast hits",
        ]
        self.parser = LogParser(logname, needles)

    def parse(self, line):
        return self.parser.parse(line)

    def print(self, output):
        return self.parser.print(output)

class KTFrostbolt:
    """
    9/28 22:50:37.695  Kel'Thuzad begins to cast Frostbolt.

    -- seems those are from a different uninterruptable ability, ignore them for now.
    9/28 22:50:46.086  Kel'Thuzad 's Frostbolt hits Dregoth for 2624 Frost damage.
    9/28 22:52:16.775  Kel'Thuzad 's Frostbolt was resisted by Belayer.
    9/28 22:50:14.102  Kel'Thuzad 's Frostbolt is absorbed by Srj.

    9/28 22:52:56.103  Srj 's Kick hits Kel'Thuzad for 66.
    9/28 22:50:38.406  Mupsi 's Kick crits Kel'Thuzad for 132.
    9/28 22:52:27.732  Jaekta 's Pummel hits Kel'Thuzad for 17.
    9/28 22:52:51.129  Psykhe 's Shield Bash hits Kel'Thuzad for 33.
    9/28 22:50:24.408  Melevolence 's Pummel was parried by Kel'Thuzad.

    """
    def __init__(self):
        logname = 'KT Frostbolt Log'
        needles = [
            "Kel'Thuzad begins to cast Frostbolt",
            # "Kel'Thuzad 's Frostbolt",
            "Kick ((hits)|(crits)|(was parried by)) Kel'Thuzad",
            "Pummel ((hits)|(crits)|(was parried by)) Kel'Thuzad",
            "Shield Bash ((hits)|(crits)|(was parried by)) Kel'Thuzad",
        ]
        self.parser = LogParser(logname, needles)

    def parse(self, line):
        return self.parser.parse(line)

    def print(self, output):
        return self.parser.print(output)


class KTFrostblast:
    """
    9/28 22:52:03.404  Bloxie is afflicted by Frost Blast (1).
    9/28 22:52:03.404  Dyrachyo is afflicted by Frost Blast (1).
    9/28 22:52:03.404  Killanime is afflicted by Frost Blast (1).
    9/28 22:52:03.404  Melevolence is afflicted by Frost Blast (1).
    9/28 22:52:03.414  Djune is afflicted by Frost Blast (1).
    9/28 22:52:04.449  Kel'Thuzad 's Frost Blast is absorbed by Djune.
    9/28 22:52:04.449  Kel'Thuzad 's Frost Blast hits Melevolence for 1315 Frost damage.
    9/28 22:52:04.449  Kel'Thuzad 's Frost Blast hits Killanime for 1605 Frost damage.
    9/28 22:52:04.449  Kel'Thuzad 's Frost Blast hits Dyrachyo for 1546 Frost damage.
    """
    def __init__(self):
        logname = 'KT Frost Blast Log'
        needles = [
            r"is afflicted by Frost Blast \(1\)",
            "Kel'Thuzad 's Frost Blast",
        ]
        self.parser = LogParser(logname, needles)

    def parse(self, line):
        return self.parser.parse(line)

    def print(self, output):
        return self.parser.print(output)



current_year = datetime.datetime.now().year

# player - consumable - count
player = collections.defaultdict(lambda: collections.defaultdict(int))

# player - consumable - unix_timestamp
last_hit_cache = collections.defaultdict(lambda: collections.defaultdict(float))

# player - buff
player_detect = collections.defaultdict(str)

# pet -> owner
pet_detect = dict()

# name -> death count
death_count = collections.defaultdict(int)

huhuran = Huhuran()
gluth = Gluth()
cthun_chain = BeamChain(logname="C'Thun Chain Log (2+)", beamname="Eye of C'Thun 's Eye Beam", chainsize=2)
fourhm_chain = BeamChain(logname="4HM Zeliek Chain Log (4+)", beamname="Sir Zeliek 's Holy Wrath", chainsize=4)
kt_shadowfissure = KTShadowFissure()
kt_frostbolt = KTFrostbolt()
kt_frostblast = KTFrostblast()


def parse_log(filename):
    with io.open(filename, encoding='utf8') as f:
        for line in f:
            # skip some ambiguous buffs
            if 'Prayer of Shadow Protection' in line:
                continue
            if 'gains Holy Strength (1)' in line:
                continue
            if 'Berserker Rage Effect' in line:
                continue

            if 'gains' in line and '(1)' in line:
                if gains_consumable(line):
                    continue
                if player_detected(line):
                    continue


            if tea_with_sugar(line):
                continue
            if great_rage(line):
                continue
            if mana_potion(line):
                continue
            if mana_rune(line):
                continue
            if health_potion(line):
                continue
            if begins_to_cast_consumable(line):
                continue
            if casts_consumable(line):
                continue
            if hits_consumable(line):
                continue

            if consolidated_log(line):
                continue
            if deaths_log(line):
                continue


            if huhuran.parse(line):
                continue
            if cthun_chain.parse(line):
                continue
            if gluth.parse(line):
                continue
            if fourhm_chain.parse(line):
                continue
            if kt_shadowfissure.parse(line):
                continue
            if kt_frostbolt.parse(line):
                continue
            if kt_frostblast.parse(line):
                continue



def generate_output():



    output = io.StringIO()

    print("""Notes:
    - The report is generated using the combat log.
    - Jujus and many foods are not in the combat log, so they can't be easily counted.
    - Dragonbreath chili and goblin sappers have only "on hit" messages, so their usage is estimated based on timestamps and cooldowns.
    - Mageblood and some other mana consumes are "mana regeneration" in the combat log, can't tell them apart.

    """, file=output)


    # remove pets
    for pet in pet_detect:
        if pet in player_detect:
            del player_detect[pet]

    # add players detected
    for name in player_detect:
        player[name]


    names = sorted(player.keys())
    for name in names:
        print(name, f'deaths:{death_count[name]}', file=output)
        cons = player[name]
        consumables = sorted(cons.keys())
        for consumable in consumables:
            count = cons[consumable]
            print('  ', consumable, count, file=output)
        if not consumables:
            print('  ', '<nothing found>', file=output)


    huhuran.print(output)
    cthun_chain.print(output)
    gluth.print(output)
    fourhm_chain.print(output)
    kt_shadowfissure.print(output)
    kt_frostbolt.print(output)
    kt_frostblast.print(output)


    print(f"\n\nPets:", file=output)
    for pet in pet_detect:
        print('  ', pet, 'owned by', pet_detect[pet], file=output)

    print(output.getvalue())
    return output


def get_user_input():
    parser = argparse.ArgumentParser()
    parser.add_argument('logpath', help='path to WoWCombatLog.txt')
    parser.add_argument('--pastebin', action='store_true', help='upload result to a pastebin and return the url')
    parser.add_argument('--open-browser', action='store_true', help='used with --pastebin. open the pastebin url with your browser')
    args = parser.parse_args()

    return args


def upload_pastebin(output):
    data = output.getvalue()

    username, password = 'summarize_consumes', 'summarize_consumes'
    auth = requests.auth.HTTPBasicAuth(username, password)
    data = output.getvalue().encode('utf8')
    response = requests.post(
        url='http://ix.io',
        files={'f:1': data},
        auth=auth,
        timeout=30,
    )

    print(response.text)
    if 'already exists' in response.text:
        print("didn't get a new url")
        import pdb;pdb.set_trace()
        raise RuntimeError('no url')

    url = response.text.strip().split('\n')[-1]
    return url


def open_browser(url):
    print(f'opening browser with {url}')
    webbrowser.open(url)


def main():

    args = get_user_input()

    parse_log(filename=args.logpath)
    output = generate_output()

    if not args.pastebin: return
    url = upload_pastebin(output)

    if not args.open_browser: return
    open_browser(url)


if __name__ == '__main__':
    main()