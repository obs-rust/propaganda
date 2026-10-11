"""One-off: rebuild data/keyframes.json from the hand annotations (after a bad in-place merge)."""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
X2 = lambda keys, H: [[t, x * 2, y * 2, H] for t, x, y in keys]
K = 2.88
D = lambda keys, H=430: [[t, round(x * K), round(y * K), H] for t, x, y in keys]
W = lambda keys, H=430: [[t, x, y, H] for t, x, y in keys]
e = lambda note, keys=None, **kw: {"note": note, "keys": keys if keys is not None else kw.pop("keys"), **kw}
horde = [
 e("horned leader with axe", [[4.6,750,355,95],[5.6,700,285,190],[6.1,630,235,230],[6.3,605,190,290],[6.45,580,160,340],[6.55,560,150,380]]),
 e("far-left horned", [[4.6,330,355,95],[5.6,270,290,185],[6.1,300,255,230],[6.3,265,225,270],[6.45,225,190,300],[6.55,160,170,330]]),
 e("right horned", [[4.6,650,385,80],[5.6,765,375,110],[6.1,770,270,200],[6.3,820,250,250],[6.45,880,215,280],[6.55,905,210,300]]),
 e("centre runner", [[4.6,535,360,95],[5.6,490,335,140],[6.1,520,290,190],[6.3,520,265,220],[6.45,630,290,200],[6.55,690,255,240]]),
 e("left-mid runner", [[4.6,430,355,95],[5.6,360,310,160],[6.1,380,345,140],[6.3,360,340,150],[6.45,290,300,200],[6.55,265,285,220]]),
 e("far-right brute, emerges late", [[6.1,935,215,240],[6.3,1020,190,280],[6.45,1075,180,310],[6.55,1110,175,330]]),
 e("small hunched, left of centre", [[4.6,590,375,85],[5.6,600,350,110],[6.1,440,355,120],[6.3,440,345,140],[6.45,380,330,160],[6.55,365,315,180]]),
 e("far-left dark, exits left edge", [[5.6,215,300,170],[6.1,135,240,260],[6.3,95,190,300],[6.45,50,140,330],[6.55,25,130,350]]),
 e("far-right faint, right edge", [[4.6,890,370,90],[5.6,1060,330,150],[6.1,1230,320,180],[6.3,1250,280,220],[6.45,1280,240,260],[6.55,1300,220,280]]),
 e("background runner by the light", [[4.6,680,385,75],[5.6,545,340,130],[6.1,560,320,140],[6.3,720,355,110],[6.45,720,340,130],[6.55,730,330,140]]),
 e("behind right horned", [[5.6,830,350,110],[6.1,860,310,150],[6.3,790,300,160],[6.45,810,325,180],[6.55,830,300,200]]),
 e("left horned flail-bearer", [[4.6,470,365,90],[5.6,355,315,160],[6.1,225,290,200],[6.3,180,260,230],[6.45,150,250,240],[6.55,120,240,250]]),
]
melee = [
 e("dark cleaver brute: charges in from the left edge, then fights on the left",
   X2([[8.85,30,200],[8.9,80,190],[9.0,220,160],[9.1,230,180],[9.2,100,250],[9.3,60,220],[9.4,165,200],[9.5,180,240],[9.6,40,190],[9.7,120,180],[9.8,150,170],[9.9,100,230]],500)),
 e("fleshy enemy grabbed then impaled, centre", X2([[9.4,420,130],[9.5,390,130],[9.6,240,270],[9.7,330,240],[9.8,380,200],[9.9,420,190]],600)),
 e("bloody-headed enemy held low, left", X2([[10.0,360,280],[10.1,300,300],[10.2,290,290],[10.3,270,300],[10.4,230,340],[10.5,180,380],[10.6,190,380]],400)),
 e("exposed-flesh mutant wrestling a marine; head above frame", X2([[10.1,560,20],[10.2,580,10],[10.3,560,10],[10.4,520,10],[10.5,430,10],[10.6,480,10],[10.7,250,20],[10.8,330,200]],900)),
 e("small dying enemy on the ground, bottom left", X2([[10.9,150,340],[11.0,180,360],[11.1,190,350],[11.2,220,370],[11.3,230,390],[11.4,270,370],[11.5,320,380]],320)),
 e("spiky enemy hauled up over a marine, shot; head bursts ~11.85",
   X2([[10.9,340,20],[11.0,420,20],[11.1,500,20],[11.2,560,20],[11.3,620,20],[11.4,600,20],[11.5,620,20],[11.6,640,30],[11.7,700,60],[11.8,480,150],[11.85,470,160]],700), fade_out=2),
 e("fleshy cultist in the mass at the bottom of the collision", X2([[9.0,130,420],[9.1,420,320],[9.2,300,330],[9.3,220,400]],420)),
]
cultist = [e("hooded cultist beside a marine", label="server crash: stack overflow", keys=[[13.56,560,150,820],[13.6,550,140,820],[13.7,510,160,820],[13.8,530,100,820],[13.9,550,60,820],[14.0,560,80,820],[14.1,560,60,820],[14.17,560,60,820]])]
longtake = [
 e("sword cultist right, close behind the walking hero", X2([[16.0,745,215],[16.5,785,225],[17.0,700,150],[17.5,750,170]],520)),
 e("enemy hanging top-left, then runner left", X2([[16.0,200,40],[16.5,150,40],[17.0,180,150],[17.4,200,170]],420)),
 e("axe brute bottom right", X2([[17.4,820,330],[17.8,760,250]],560)),
 e("far runner left in the fog", X2([[18.4,190,190],[18.7,170,200],[18.9,150,210]],360)),
 e("runner far left", D([[16.75,64,127],[17.0,156,137],[17.25,60,60]])),
 e("horned enemy centre-right", D([[17.0,466,137],[17.25,480,114],[17.5,514,114],[17.75,466,164]])),
 e("brute far right", D([[16.75,544,137],[17.0,546,170],[17.25,590,234]],500)),
 e("horned far left", D([[22.25,44,150],[22.5,96,165],[22.75,60,172]],360)),
 e("spiky horned, thrown", D([[22.75,180,192],[23.0,104,150],[23.25,86,100]])),
 e("left runners", D([[24.25,40,45],[24.5,124,50],[24.75,66,45]],360)),
 e("horned charger right, head bursts", D([[26.0,630,140],[26.25,506,140],[26.5,620,114],[26.75,584,114],[27.0,546,114]]), fade_out=2),
 e("creature centre", D([[26.75,384,114],[27.0,376,154],[27.25,480,71],[27.5,384,41]])),
 e("runner right, cut down", D([[28.0,610,150],[28.25,554,145],[28.5,466,200]]), fade_out=2),
 e("horned left", D([[28.75,110,157],[29.0,104,112],[29.25,66,77]],400)),
 e("figure right", D([[29.0,600,140],[29.25,596,137],[29.5,600,140]],400)),
 e("horned right, late", D([[30.0,626,40],[30.25,550,40],[30.4,540,45]],400)),
 e("leaping cultist left (19 s)", W([[18.83,420,340],[19.0,280,180],[19.17,300,540]])),
 e("caped figure far left", W([[18.5,90,520],[18.83,80,500],[19.0,60,510]],400)),
 e("sword cultist right (19 s)", W([[18.83,1280,480],[19.0,1400,500],[19.17,1560,480],[19.33,1720,440]])),
 e("club raiser grappled by hero", W([[19.33,440,580],[19.5,640,480],[19.67,540,520],[19.75,576,452],[20.0,530,553]])),
 e("hooded runner far right", W([[19.5,1520,440],[19.67,1660,520],[20.0,1624,481],[20.25,1745,279]],380)),
 e("runner left-mid (17 s)", W([[16.83,500,340],[17.0,460,420],[17.17,360,300]])),
 e("close brute far left (17 s)", W([[16.83,120,300],[17.0,60,240],[17.17,60,240]],600)),
 e("runner right (17 s)", W([[16.83,1660,440],[17.0,1580,420],[17.17,1740,380]])),
 e("small figure behind hero (17 s)", W([[16.7,660,460],[16.83,640,460],[16.95,630,460]],300)),
 e("left cultist (20 s)", W([[20.0,360,540],[20.17,120,500],[20.3,80,500]])),
 e("far right edge (20 s)", W([[19.9,1900,600],[20.0,1900,600],[20.15,1890,600]])),
 e("brute grabbed, head bursts (21 s)", W([[20.5,1469,115],[20.83,1480,300],[21.0,1440,320],[21.17,1320,340],[21.3,1300,360]],600)),
 e("far right figure (21 s)", W([[20.9,1740,700],[21.0,1740,700],[21.17,1760,690]],350)),
 e("far figure in fog (22 s)", W([[21.9,1480,420],[22.0,1480,420],[22.1,1490,420]],350)),
 e("grappled enemy right (22 s)", W([[22.0,1600,400],[22.17,1700,380],[22.3,1720,380]])),
 e("far left figure (22 s)", W([[22.05,90,420],[22.17,80,420],[22.3,80,420]],350)),
 e("horned left (23 s)", W([[22.83,240,500],[23.0,280,560],[23.17,300,600]])),
 e("severed head flying (23 s)", W([[23.0,480,480],[23.17,340,200],[23.3,300,150]],200)),
 e("leaping cultist left (25 s)", W([[24.75,220,400],[24.83,200,400],[25.0,160,420]])),
 e("flying head (25 s)", W([[24.83,380,220],[25.0,260,200],[25.15,200,210]],200)),
 e("runner right (25 s)", W([[24.83,1660,460],[25.0,1800,320],[25.17,1740,400]])),
 e("horned charger (25 s)", W([[25.33,1600,380],[25.5,1400,440],[25.67,1280,300]],500)),
 e("far left figure (25 s)", W([[25.17,140,440],[25.33,160,440],[25.5,260,520],[25.67,280,500]],350)),
 e("far right figure (25 s)", W([[25.5,1640,480],[25.67,1660,440],[25.8,1670,440]],350)),
]
longtake += [
 e('horned enemy right of hero (18 s)', [[17.75, 1410, 450, 430], [17.83, 1425, 480, 430], [18.0, 1410, 570, 430], [18.17, 1440, 600, 430]]),
 e('club cultist centre (18.5 s)', [[18.5, 1065, 480, 430], [18.67, 1110, 570, 430], [18.83, 1290, 600, 430]]),
 e('far right runner (20.3 s)', [[20.17, 1680, 420, 380], [20.33, 1770, 390, 380], [20.5, 1800, 390, 380]]),
 e('horned far centre (21.5 s)', [[21.4, 1020, 300, 360], [21.5, 1050, 300, 360], [21.67, 1380, 270, 360]]),
 e('horned bottom-left (23.2 s)', [[23.0, 240, 660, 430], [23.17, 180, 690, 430], [23.33, 210, 720, 430]]),
 e('horned left figure (24.5 s)', [[24.33, 300, 510, 420], [24.5, 240, 450, 420], [24.67, 270, 450, 420]]),
 e('far runner centre-right (26 s)', [[25.9, 1200, 420, 380], [26.0, 1230, 390, 380], [26.17, 1320, 420, 380], [26.33, 1440, 450, 380], [26.5, 1560, 450, 380]]),
 e('far right figure (26.5 s)', [[26.33, 1800, 420, 380], [26.5, 1800, 450, 380], [26.67, 1770, 450, 380]]),
 e('horned charger centre (26.7 s)', [[26.67, 960, 120, 520], [26.83, 1110, 270, 520], [27.0, 1410, 390, 520]]),
 e('horned brute right (27 s)', [[26.83, 1680, 360, 480], [27.0, 1680, 300, 480], [27.17, 1800, 480, 480]]),
 e('horned enemy centre (27.5 s)', [[27.33, 1260, 450, 480], [27.5, 1080, 390, 480], [27.67, 990, 360, 480]]),
 e('runner right, grabbed (28.5 s)', [[28.33, 1560, 450, 450], [28.5, 1410, 390, 450], [28.67, 1500, 450, 450]]),
 e('left figures (29.3 s)', [[29.17, 180, 300, 380], [29.33, 180, 270, 380], [29.5, 240, 300, 380]]),
 e('second left figure (29.3 s)', [[29.17, 480, 330, 380], [29.33, 450, 270, 380], [29.5, 510, 300, 380]]),
]
longtake += [
 e('horned figure behind grapple (21.6 s, user-flagged)', [[21.45,1050,320,330],[21.6,1123,356,330],[21.75,1250,330,330],[21.85,1380,300,330]], no_merge=True),
 e('far right fog figure (22 s, user-flagged)', [[21.9,1780,360,380],[22.0,1757,370,380],[22.15,1680,410,380],[22.3,1598,454,380],[22.45,1560,470,380]], no_merge=True),
]
longtake += [e("gun brute, before the cut (29 s, user-flagged)", label="graphics driver crash", no_merge=True,
               keys=[[29.2,600,250,600],[29.5,625,246,620],[29.8,640,240,640],[30.1,650,235,660],[30.4,655,230,680]])]
late = [e("spiked enemy right (close-up)", D([[30.5,574,151],[30.75,446,101],[31.0,500,200],[31.7,520,210]],450), label="graphics driver crash", feature=3, violence=5, violence_manual=True)]
brute = [
 e("horned gun brute (close-up)", label="graphics driver crash", feature=2, violence=5, violence_manual=True, keys=D([[31.85,560,30],[32.0,534,37],[32.25,546,40],[32.5,580,24],[33.0,580,24]],800)),
 e("spiky blade cultist (close-up, one figure 32.5-34.9 s)", feature=1, violence=5, violence_manual=True, keys=D([[32.5,380,154],[32.75,364,154],[33.0,366,154],[33.75,356,81],[34.0,380,80],[34.25,354,160],[34.5,426,110],[34.75,410,67],[34.9,410,67]],500)),
]

finale = [
 {"name": "breath", "start": 34.95, "end": 41.574, "crop_origin": [0, 0], "no_auto": True,
  "_note": "pensive pause after the battle: URL breathes in on the music swell (36.5-37.2) and is gone before his hand rises to the helmet (~39.3)",
  "title": {"text": "github.com/obs-rust", "from": 36.5, "to": 41.574, "x": 0.17, "y": 0.30, "scale": 0.55,
            "fade_in_frames": 22, "fade_frames": 2}, "enemies": []},
 {"name": "tank44", "start": 44.268, "end": 45.936, "crop_origin": [0, 0], "fade_in": 4, "fade_out": 1, "no_auto": True, "enemies": [
   e("gatling tank, distant, gun not visible (anchor: midpoint of the two headlights)", label="audio stutter", offset=[0, 0],
     keys=[[44.27,1626,486,130],[45.93,1626,486,130]])]},
 {"name": "tank47", "start": 46.971, "end": 48.15, "crop_origin": [0, 0], "fade_in": 1, "fade_out": 2, "no_auto": True, "enemies": [
   e("gatling tank close-up (anchor: midpoint of the two headlights)", label="audio stutter", offset=[0, 0],
     keys=[[46.98,1222,690,500],[48.14,1222,690,500]])]},
 {"name": "tank0", "start": 59.200, "end": 59.934, "crop_origin": [0, 0], "fade_in": 3, "fade_out": 1, "no_auto": True, "enemies": [
   e("gatling tank, distant (anchor: midpoint of the two headlights)", label="audio stutter", offset=[0, 0],
     keys=[[59.2,1215,476,130],[59.93,1215,476,130]])]},
 {"name": "tank1", "start": 59.934, "end": 61.603, "crop_origin": [0, 0], "fade_in": 1, "fade_out": 3, "no_auto": True, "enemies": [
   e("gatling tank, zoomed (anchor: midpoint of the two headlights)", label="audio stutter", offset=[0, 0],
     keys=[[59.94,1349,366,420],[61.55,1349,366,420]]),
   e("fast car (anchor: midpoint of headlights, label 10% right)", label="uint8_t overflow", offset=[0.10, 0],
     keys=[[60.2, 570, 705, 300], [60.4, 488, 630, 300], [60.6, 458, 640, 300], [60.8, 578, 713, 300], [61.0, 773, 563, 300], [61.2, 900, 578, 300], [61.45, 950, 570, 300]])]},
 {"name": "car", "start": 62.270, "end": 62.737, "crop_origin": [0, 0], "fade_in": 1, "fade_out": 1, "no_auto": True, "enemies": [
   e("fast car approaching (anchor: headlights, offset to the rider's head)", label="uint8_t overflow", offset=[0.10, -0.11],
     keys=[[62.28, 1238, 525, 300], [62.4, 1208, 525, 300], [62.6, 1300, 480, 300], [62.73, 1330, 470, 300]])]},
 {"name": "carboom", "start": 62.737, "end": 64.005, "crop_origin": [0, 0], "fade_in": 1, "fade_out": 1, "no_auto": True, "enemies": [
   e("car explodes; rider's heroic impact (anchor: headlight, offset to the head)", label="uint8_t overflow", offset=[-0.10, -0.20],
     keys=[[62.74, 1605, 390, 300], [63.0, 1635, 390, 300], [63.4, 1630, 390, 300], [63.99, 1630, 390, 300]])]},
 {"name": "tank2", "start": 66.808, "end": 68.543, "crop_origin": [0, 0], "fade_in": 1, "fade_out": 1, "no_auto": True, "enemies": [
   e("gatling tank, side view (FIXED screen position: upper-right third, above the tank)", label="audio stutter",
     keys=[[66.82,1500,330,300],[68.54,1500,330,300]], fixed=True)]},
 {"name": "spiky", "start": 68.710, "end": 72.0, "crop_origin": [0, 0], "fade_in": 4, "fade_out": 6, "no_auto": True, "enemies": [
   e("spiky baddie vs marine (FIXED at the barycentre of the fight)", label="anti ai policy", keys=[[68.72,1392,442,500],[71.6,1392,442,500]])]},
 {"name": "grenade", "start": 72.6, "end": 73.6, "crop_origin": [0, 0], "fade_in": 2, "fade_out": 3, "no_auto": True, "enemies": [
   e("hand with grenade (labelled before the grenade shows)", label="unit test", keys=[[72.62,1260,660,600],[72.85,1300,620,600],[73.1,1370,575,600],[73.45,1390,568,600]], smooth=4.0)]},
 {"name": "charge", "start": 83.401, "end": 89.06, "crop_origin": [0, 0], "fade_in": 6, "fade_out": 8, "no_auto": True, "enemies": [
   e("charge on the gatling tank (anchor: the big hull spike, label just left of the charge)", label="e2e tests", offset=[-0.075, -0.08],
     keys=[[84.0,1200,380,500],[84.5,1200,380,500],[85.0,1200,380,500]]),
   e("chained sarcophagus dragged by the marine (two-point anchor: chain hand, then the lid's lower trim)", label="Address Sanitizer",
     keys=[[85.3,0,0,0]],
     axis=[[85.3,965,730,1375,730],[86.0,935,850,1345,850],[86.5,845,880,1255,880],[87.0,965,880,1375,880],
           [87.5,1200,945,1510,955],[87.75,1150,905,1450,918],[88.0,1020,900,1400,918],[88.25,975,850,1400,870],
           [88.5,950,805,1385,826],[88.75,870,765,1340,787],[89.0,770,740,1300,760],[89.06,760,738,1295,758]], fade_out=1)]},
]
doc = ("Hand-placed (vision) keyframes per enemy; heroes are never keyed. Each key is [time_s, head_x, head_y, figure_height] "
       "in work pixels (1920x960 frame) minus the shot's crop_origin. tools/assign_labels.py picks label_id (violence x screen time).")
d = {"_doc": doc, "video": "marines-fixing-bugs.webm", "crop_origin": [300, 80], "work_size": [1920, 960], "shots": [
 {"name": "intro", "start": 0.0, "end": 2.035, "hold_to_cut": True,
  "title": {"text": "AI vs", "from": 0.0, "to": 2.035, "y": 0.56, "fade_frames": 9, "fade_out_frames": 6, "beats": [[0.0, "AI"], [0.75, "AI vs"]]}, "enemies": []},
 {"name": "horde", "start": 2.035, "end": 6.64, "hold_to_cut": True,
  "title": {"text": "obs-studio bugs", "from": 4.035, "to": 6.64, "y": 0.56}, "enemies": []},
 {"name": "melee", "start": 6.64, "end": 13.547, "crop_origin": [0, 0], "fade_in": 4, "fade_out": 6, "enemies": melee},
 {"name": "cultist", "start": 13.547, "end": 14.181, "crop_origin": [0, 0], "fade_in": 4, "fade_out": 4, "enemies": cultist},
 {"name": "longtake", "start": 15.768, "end": 30.416, "crop_origin": [0, 0], "fade_in": 4, "fade_out": 6,
  "hero_masks": ["pilot", "s19", "s24"], "enemies": longtake},
 {"name": "late", "start": 30.416, "end": 31.751, "crop_origin": [0, 0], "fade_in": 4, "fade_out": 4, "no_auto": True, "enemies": late},
 {"name": "brute", "start": 31.818, "end": 34.95, "crop_origin": [0, 0], "fade_in": 4, "fade_out": 4, "no_auto": True, "enemies": brute},
] + finale}
import re as _re
for _s in d["shots"]:  # stable ids: the label lock is keyed by these, never by list position
    for _e in _s["enemies"]:
        _e.setdefault("id", _s["name"] + "/" + _re.sub(r"[^a-z0-9]+", "-", _e["note"].lower()).strip("-")[:60])
(ROOT / "data/keyframes.json").write_text(json.dumps(d, indent=1) + "\n")
print(sum(len(s["enemies"]) for s in d["shots"]), "enemies restored")
