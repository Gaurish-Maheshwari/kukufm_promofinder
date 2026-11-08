#!/usr/bin/env python3
"""Generate the synthetic demo show in data/sample/.

"The Maid Who Owns the Mansion" is ORIGINAL content written for this repo
(not Kuku's input pack). It is rendered in six different screenplay layouts on
purpose, to exercise the parser the way a real, messy input folder would:

  show/Episode_01.txt … Episode_03.txt  bracketed  [00:00:07] NAME: line
  show/more/Ep04_table.txt              pipe table  00:04 - 00:09 | DIALOGUE | NAME | line
  show/more/Ep05.docx                   Word, mm:ss without brackets, untagged actions
  show/more/Episode 6 (classic).txt     classic layout: TC line, NAME line, (parenthetical), dialogue
  show/Episodes_07-08.pdf               two episodes in one PDF with page furniture
  sample_show.zip                       everything above, with the PDF inside a nested zip

Also writes manual_promos_sample.csv: promos picked by hand (by the author, before
running the tool) to demo the side-by-side comparison.
"""
from __future__ import annotations

import io
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "sample"

A, S, D, X = "action", "scene", "dialogue", "sfx"

# (seconds, kind, speaker, text, manner)
EPISODES: dict[int, tuple[str, list[tuple]]] = {
    1: ("The Wine", [
        (0, S, None, "INT. CROSS MANSION BALLROOM – NIGHT", None),
        (0, A, None, "A crystal chandelier glitters over a crowded engagement party.", None),
        (3, A, None, "AVA, in a grey maid's uniform, carries a tray of champagne through the guests.", None),
        (7, D, "CHLOE", "Careful, maid. That dress costs more than your life.", None),
        (11, A, None, "Chloe deliberately bumps the tray. Glasses shatter across the marble floor.", None),
        (14, D, "VIVIAN", "Clumsy girl! Clean it up. On your knees.", None),
        (18, A, None, "Guests laugh. Ava kneels slowly, picking up shards with bare hands.", None),
        (23, D, "AVA", "Yes, Mrs. Cross.", None),
        (25, A, None, "Ethan watches from the staircase, jaw tight.", None),
        (29, D, "ETHAN", "Mother, that's enough.", None),
        (32, D, "CHLOE", "Darling, don't waste your pity on the help.", None),
        (36, A, None, "Chloe picks up a full glass of red wine and throws it in Ava's face.", None),
        (39, D, "CHLOE", "Now you match the floor.", None),
        (42, A, None, "The room erupts in laughter. Wine drips from Ava's chin.", None),
        (46, D, "AVA", "You'll regret this, Miss Vance.", "quietly"),
        (50, D, "CHLOE", "Regret? You're nothing. A nobody who scrubs our toilets.", None),
        (55, S, None, "INT. SERVANTS' QUARTERS – NIGHT", None),
        (55, A, None, "Ava washes the wine from her face in a cracked mirror.", None),
        (60, A, None, "Marcus, the old butler, slips in and closes the door behind him.", None),
        (63, D, "MARCUS", "Miss Ava, you don't have to endure this. Not for one more day.", None),
        (68, D, "AVA", "Not yet, Marcus. I need to see who they really are.", None),
        (72, D, "MARCUS", "Your grandfather's will is read on Friday. After that, this house is yours.", None),
        (78, D, "AVA", "Then let them enjoy it until Friday.", None),
        (82, X, None, "Footsteps outside. The door handle turns.", None),
        (85, A, None, "Ava and Marcus freeze.", None),
        (88, D, "ETHAN", "Who's in there with you?", "O.S."),
        (92, A, None, "The door swings open. Ethan stands in the doorway.", None),
        (95, A, None, "SMASH CUT TO BLACK.", None),
    ]),
    2: ("The Ring", [
        (0, S, None, "INT. SERVANTS' QUARTERS – CONTINUOUS", None),
        (0, A, None, "Ethan steps inside. Marcus quickly bows.", None),
        (3, D, "MARCUS", "Young master. I was only bringing her a towel.", None),
        (7, D, "ETHAN", "Leave us.", None),
        (9, A, None, "Marcus exits. Ethan studies Ava's stained uniform.", None),
        (13, D, "ETHAN", "Why didn't you fight back?", None),
        (16, D, "AVA", "Because a maid who fights back loses her job.", None),
        (20, D, "ETHAN", "You don't talk like a maid.", None),
        (23, A, None, "He reaches out and wipes a drop of wine from her cheek. Ava steps back.", None),
        (27, D, "AVA", "Goodnight, Mr. Cross.", None),
        (30, S, None, "INT. CROSS MANSION KITCHEN – MORNING", None),
        (30, A, None, "The staff prepare breakfast. Ava polishes silverware.", None),
        (35, A, None, "Chloe sweeps in wearing a silk robe.", None),
        (38, D, "CHLOE", "My engagement ring. It's gone. Someone in this kitchen took it.", None),
        (43, A, None, "The staff go silent.", None),
        (45, D, "CHLOE", "Search her. The new girl. She was in Ethan's study last night.", None),
        (50, A, None, "A guard empties Ava's apron pocket. A diamond ring falls onto the counter.", None),
        (54, A, None, "Gasps around the kitchen.", None),
        (56, D, "AVA", "I've never seen that ring before.", None),
        (59, D, "CHLOE", "Liar! Call the police.", None),
        (62, D, "VIVIAN", "No police. Scandal is bad for the company. Just throw her out.", None),
        (67, A, None, "Two guards grab Ava by the arms and drag her toward the door.", None),
        (71, D, "AVA", "Check the cameras! The study has cameras!", None),
        (75, A, None, "Chloe's smile flickers for half a second.", None),
        (78, D, "CHLOE", "The cameras were broken last week. What a shame.", None),
        (82, S, None, "EXT. CROSS MANSION GATE – DAY", None),
        (82, A, None, "Ava is shoved through the iron gate onto the wet pavement. Rain begins to fall.", None),
        (87, A, None, "A black Rolls-Royce pulls up beside her. The rear window rolls down.", None),
        (91, D, "MR. HALE", "Miss Lockwood? Your grandfather's lawyer. We need to talk—now.", None),
        (96, A, None, "Ava looks back at the mansion. Her eyes harden.", None),
    ]),
    3: ("The Lobby", [
        (0, S, None, "INT. ROLLS-ROYCE – DAY", None),
        (0, D, "MR. HALE", "Your grandfather owned sixty percent of Cross Holdings. Through you.", None),
        (5, D, "AVA", "So the Crosses have been living in my house.", None),
        (8, D, "MR. HALE", "And spending your money. The will makes you chairwoman on Friday.", None),
        (13, D, "AVA", "Don't tell anyone. Not yet.", None),
        (16, S, None, "INT. CROSS HOLDINGS LOBBY – DAY", None),
        (16, A, None, "Ava, still in her uniform, walks into the glass lobby.", None),
        (20, D, "RECEPTIONIST", "Deliveries go around the back.", None),
        (23, D, "AVA", "I'm here to see the board.", None),
        (26, A, None, "The receptionist laughs and picks up the phone.", None),
        (29, D, "RECEPTIONIST", "Security, we have a cleaner who thinks she's an executive.", None),
        (33, A, None, "Chloe steps out of the elevator with Vivian.", None),
        (36, D, "CHLOE", "Oh, look. The thief came back for more.", None),
        (40, D, "VIVIAN", "Get her out before the investors see her.", None),
        (43, A, None, "A guard grabs Ava's wrist. She doesn't move.", None),
        (46, D, "AVA", "Take your hand off me. You'll want to keep this job after Friday.", None),
        (51, A, None, "The guard hesitates. Ethan walks in through the revolving door.", None),
        (55, D, "ETHAN", "What's going on here?", None),
        (58, D, "CHLOE", "The maid stole my ring, and now she's stalking you.", None),
        (62, D, "ETHAN", "Did you take it, Ava?", None),
        (65, D, "AVA", "Do you believe I did?", None),
        (68, A, None, "Ethan holds her gaze. Long silence.", None),
        (72, D, "ETHAN", "...No. I don't.", None),
        (75, A, None, "Chloe's face goes pale.", None),
        (78, D, "CHLOE", "Ethan, you're choosing a maid over your fiancée?", None),
        (82, D, "ETHAN", "I'm choosing the truth. Pull the lobby cameras from last night.", None),
        (87, A, None, "Chloe grabs Vivian's arm and leans close.", None),
        (90, D, "CHLOE", "If he sees that footage, we're both finished.", "whispering"),
        (95, A, None, "Vivian looks at Ava as if seeing her for the first time.", None),
        (98, D, "VIVIAN", "Who are you really?", None),
    ]),
    4: ("The Gala", [
        (0, S, None, "INT. SECURITY ROOM – DAY", None),
        (0, A, None, "Ethan and a technician scroll through grainy footage.", None),
        (4, D, "TECHNICIAN", "The study camera was switched off at nine. By an admin account.", None),
        (9, D, "ETHAN", "Whose account?", None),
        (11, D, "TECHNICIAN", "It's registered to... Miss Vance.", None),
        (15, A, None, "Ethan's hands curl into fists.", None),
        (18, S, None, "INT. CROSS MANSION – CHLOE'S BEDROOM – DAY", None),
        (18, A, None, "Chloe stuffs documents into a shredder.", None),
        (22, A, None, "Her phone buzzes. A message: \"He knows.\"", None),
        (25, D, "CHLOE", "No, no, no.", None),
        (27, S, None, "INT. CAFE – DAY", None),
        (27, A, None, "Ava sips coffee with Marcus. Quiet.", None),
        (31, D, "MARCUS", "The lilies in the garden are blooming early this year.", None),
        (35, D, "AVA", "Grandfather loved those lilies.", None),
        (38, D, "MARCUS", "He'd be proud of you, Miss.", None),
        (41, A, None, "The cafe door opens. Ethan walks in, breathless.", None),
        (44, D, "ETHAN", "It was Chloe. She framed you. I'm so sorry.", None),
        (48, D, "AVA", "Sorry doesn't give me back my name.", None),
        (51, D, "ETHAN", "Then let me give you something else. Come to the gala tonight. As my guest.", None),
        (57, A, None, "Marcus raises an eyebrow.", None),
        (59, D, "AVA", "As your guest? Your fiancée will be there.", None),
        (63, D, "ETHAN", "She's not my fiancée anymore.", None),
        (66, S, None, "INT. CROSS MANSION BALLROOM – NIGHT", None),
        (66, A, None, "The gala. Ava enters in a stunning midnight-blue gown. The room turns.", None),
        (71, A, None, "Chloe, at the bar, slams down her glass.", None),
        (74, D, "CHLOE", "How dare you show your face here!", None),
        (77, A, None, "Chloe raises her hand and slaps Ava hard across the face.", None),
        (80, A, None, "The music stops.", None),
        (82, A, None, "Ava slowly turns her head back and slaps Chloe twice as hard.", None),
        (85, D, "AVA", "That's for the wine. The next one is for the ring.", None),
        (89, D, "VIVIAN", "Security! Arrest this woman!", None),
        (92, A, None, "The ballroom doors burst open. Mr. Hale enters with two police officers.", None),
        (96, D, "MR. HALE", "Nobody touches the chairwoman of Cross Holdings.", None),
        (100, A, None, "Every face in the ballroom turns to Ava.", None),
    ]),
    5: ("The Chairwoman", [
        (0, S, None, "INT. CROSS MANSION BALLROOM – CONTINUOUS", None),
        (0, D, "VIVIAN", "Chairwoman? She's a maid!", None),
        (3, D, "MR. HALE", "She is Ava Lockwood. Heir to Arthur Lockwood's sixty percent.", None),
        (8, A, None, "Gasps ripple through the guests.", None),
        (10, D, "CHLOE", "That's impossible. Lockwood's granddaughter died in the fire.", None),
        (15, D, "AVA", "I didn't die, Chloe. I was hidden. From people like you.", None),
        (20, A, None, "Ethan stares at Ava, stunned.", None),
        (23, D, "ETHAN", "You lied to me this whole time?", None),
        (26, D, "AVA", "I watched. There's a difference.", None),
        (29, S, None, "EXT. CROSS MANSION GARDEN – NIGHT", None),
        (29, A, None, "Ethan finds Ava alone by the lily pond.", None),
        (33, D, "ETHAN", "Everything my family has is yours. Why didn't you take it on day one?", None),
        (38, D, "AVA", "Because I wanted to know who would be kind to a maid.", None),
        (42, D, "ETHAN", "And?", None),
        (44, D, "AVA", "You were. Only you.", None),
        (47, A, None, "Ethan steps closer. Their faces are inches apart.", None),
        (50, A, None, "Ethan kisses her.", None),
        (53, S, None, "INT. POLICE STATION – NIGHT", None),
        (53, A, None, "Chloe sits handcuffed. An officer slides a file across the table.", None),
        (57, D, "OFFICER", "Fraud, theft, falsifying evidence. You're looking at five years.", None),
        (62, D, "CHLOE", "Get me my phone. I get one call.", None),
        (65, A, None, "She dials. Someone answers.", None),
        (67, D, "CHLOE", "It's me. Plan B. Tonight.", None),
        (70, S, None, "INT. CROSS MANSION – AVA'S NEW SUITE – NIGHT", None),
        (70, A, None, "Ava unpins her hair, smiling for the first time.", None),
        (74, A, None, "A small envelope lies on her pillow. No name.", None),
        (77, A, None, "She opens the envelope. Inside, a photo of the burning Lockwood house.", None),
        (81, A, None, "Written on the back: \"The fire was no accident.\"", None),
        (85, A, None, "Behind her, the balcony curtain moves.", None),
        (88, D, "AVA", "Who's there?", None),
    ]),
    6: ("The Intruder", [
        (0, S, None, "INT. AVA'S SUITE – CONTINUOUS", None),
        (0, A, None, "A hooded figure lunges from the balcony and grabs Ava by the throat.", None),
        (3, A, None, "Ava screams. A lamp crashes to the floor.", None),
        (6, A, None, "Ethan bursts in and tackles the intruder.", None),
        (9, A, None, "The hood falls back. It's Marcus's nephew, DANNY.", None),
        (13, D, "DANNY", "I'm sorry! She paid me! Chloe paid me!", "sobbing"),
        (17, D, "ETHAN", "To do what?", None),
        (19, D, "DANNY", "To finish what her father started.", None),
        (23, A, None, "Ava goes pale.", None),
        (25, D, "AVA", "Her father... set the fire?", None),
        (28, S, None, "INT. CROSS MANSION LIBRARY – LATER", None),
        (28, A, None, "Marcus pours tea with shaking hands.", None),
        (32, D, "MARCUS", "Miss Ava, I should have told you years ago.", None),
        (36, D, "AVA", "Told me what?", None),
        (38, D, "MARCUS", "The night of the fire, Mr. Vance came to see your grandfather. They argued about the company.", None),
        (45, D, "MARCUS", "An hour later, the east wing was burning.", None),
        (49, D, "AVA", "And you said nothing?", None),
        (52, D, "MARCUS", "He threatened my family. I'm a coward, Miss.", None),
        (57, A, None, "Ava sets down her cup. Silence.", None),
        (60, D, "AVA", "Thank you for telling me now.", None),
        (63, S, None, "INT. CROSS MANSION KITCHEN – MORNING", None),
        (63, A, None, "Vivian makes coffee herself for the first time. Awkward.", None),
        (67, D, "VIVIAN", "Ava. I owe you an apology. For the knees. For everything.", None),
        (72, D, "AVA", "Apology accepted, Mrs. Cross. Breakfast is still at eight.", None),
        (76, A, None, "Vivian laughs nervously.", None),
        (78, S, None, "INT. CROSS HOLDINGS BOARDROOM – DAY", None),
        (78, A, None, "Ava takes the head of the table. The board members stand.", None),
        (82, A, None, "The door opens. A silver-haired man walks in, smiling.", None),
        (86, D, "RICHARD VANCE", "Congratulations, Miss Lockwood. I believe you have something of mine.", None),
        (91, A, None, "Chloe walks in behind him, free, wearing a visitor's badge.", None),
    ]),
    7: ("The Call", [
        (0, S, None, "INT. CROSS HOLDINGS BOARDROOM – CONTINUOUS", None),
        (0, D, "AVA", "Mr. Vance. The man who burned my family's house.", None),
        (4, D, "RICHARD VANCE", "Careful. Slander is expensive.", None),
        (7, D, "RICHARD VANCE", "I own thirty-five percent of this company. With Vivian's five, I'll own forty.", None),
        (13, D, "VIVIAN", "I'm not giving you anything, Richard.", None),
        (16, D, "RICHARD VANCE", "You will, when you see what I know about your husband's death.", None),
        (21, A, None, "Vivian goes white and sits down.", None),
        (24, S, None, "EXT. CROSS HOLDINGS ROOFTOP – DAY", None),
        (24, A, None, "Wind. Ava and Ethan at the railing.", None),
        (28, D, "ETHAN", "My father died in a car crash. That's what they told me.", None),
        (32, D, "AVA", "Maybe that's what Vance wants you to believe.", None),
        (36, D, "ETHAN", "Or maybe it's true and he's bluffing.", None),
        (39, A, None, "Ethan's phone buzzes. An unknown number.", None),
        (42, D, "ETHAN", "Hello?", None),
        (44, D, "VOICE", "Sign the shares over to Vance, or your mother learns the truth.", "V.O."),
        (49, D, "ETHAN", "What truth?", None),
        (51, D, "VOICE", "That your father was alive when the car went into the river.", "V.O."),
        (56, A, None, "The call ends. Ethan stares at the phone.", None),
        (59, S, None, "INT. HOSPITAL EXAM ROOM – NIGHT", None),
        (59, A, None, "Chloe sits on an examination bed. A doctor checks a chart.", None),
        (63, D, "DOCTOR", "Miss Vance, your results are back. You're eight weeks pregnant.", None),
        (68, A, None, "Chloe smiles slowly.", None),
        (70, D, "CHLOE", "Perfect. Ethan can never leave me now.", None),
        (74, A, None, "Around the corner, Ava stands frozen, holding a bouquet of lilies.", None),
        (78, D, "AVA", "Eight weeks...", "whispering"),
    ]),
    8: ("The Test", [
        (0, S, None, "INT. CROSS MANSION LIVING ROOM – DAY", None),
        (0, A, None, "Chloe drops an ultrasound photo on the coffee table in front of Ethan.", None),
        (4, D, "CHLOE", "Congratulations, Daddy.", None),
        (6, D, "ETHAN", "That's not possible. We haven't been together in months.", None),
        (11, D, "CHLOE", "Count again, darling. Eight weeks. The night of your birthday.", None),
        (16, A, None, "Ethan turns to Ava. Ava looks away.", None),
        (19, D, "AVA", "I think I should go.", None),
        (22, D, "ETHAN", "Ava, wait—", None),
        (24, S, None, "EXT. LOCKWOOD FAMILY CEMETERY – DAY", None),
        (24, A, None, "Ava places lilies on her grandfather's grave.", None),
        (28, D, "AVA", "You built everything for me, Grandpa. And I still can't keep one person.", None),
        (34, A, None, "Footsteps behind her. Marcus.", None),
        (37, D, "MARCUS", "Miss, there's something about that ultrasound. The clinic name.", None),
        (42, D, "AVA", "What about it?", None),
        (44, D, "MARCUS", "It closed two years ago. Mr. Vance owned it.", None),
        (49, A, None, "Ava turns slowly.", None),
        (51, D, "AVA", "Then the baby is a lie.", None),
        (54, D, "MARCUS", "Or the baby is real... and the father isn't Ethan.", None),
        (59, S, None, "INT. CROSS MANSION NURSERY – NIGHT", None),
        (59, A, None, "Ethan stands among paint cans, staring at an empty crib.", None),
        (63, A, None, "Chloe enters holding a paternity test envelope.", None),
        (66, D, "CHLOE", "The DNA results. Open it. Prove you're the father.", None),
        (70, A, None, "Ethan tears the envelope. Ava appears in the doorway.", None),
        (73, D, "AVA", "Before you read that, Ethan, ask her who paid for the test.", None),
        (77, A, None, "Chloe spins around.", None),
        (79, D, "CHLOE", "You—", None),
        (80, A, None, "Ethan unfolds the paper. His eyes widen.", None),
        (83, D, "ETHAN", "This says the father is—", None),
        (85, A, None, "SMASH CUT TO BLACK.", None),
    ]),
}

TITLE = "THE MAID WHO OWNS THE MANSION"


def tc(sec: float, hours: bool = False) -> str:
    m, s = divmod(int(sec), 60)
    return f"00:{m:02d}:{s:02d}" if hours else f"{m:02d}:{s:02d}"


def ends(beats):
    out = []
    for k, b in enumerate(beats):
        nxt = next((x[0] for x in beats[k + 1:] if x[0] > b[0]), b[0] + 3)
        out.append(nxt)
    return out


def render_bracket(n, title, beats) -> str:
    L = [f"{TITLE}", f"EPISODE {n}: {title}", ""]
    scene_no = 0
    for (t, k, spk, text, manner) in beats:
        if k == S:
            scene_no += 1
            L += ["", f"SCENE {scene_no} — {text} [{tc(t, True)}]"]
        elif k == D:
            m = f" ({manner})" if manner else ""
            L.append(f"[{tc(t, True)}] {spk}{m}: {text}")
        elif k == X:
            L.append(f"[{tc(t, True)}] SFX: {text}")
        else:
            L.append(f"[{tc(t, True)}] ACTION: {text}")
    return "\n".join(L) + "\n"


def render_pipe(n, title, beats) -> str:
    L = [f"Episode {n} | {title}", "TIME | TYPE | CHARACTER | TEXT"]
    for (t, k, spk, text, manner), e in zip(beats, ends(beats)):
        rng = f"{tc(t)} - {tc(e)}"
        if k == S:
            L.append(f"{rng} | SCENE | {text}")
        elif k == D:
            txt = f"({manner}) {text}" if manner else text
            L.append(f"{rng} | DIALOGUE | {spk} | {txt}")
        else:
            L.append(f"{rng} | ACTION | {text}")
    return "\n".join(L) + "\n"


def render_classic(n, title, beats) -> str:
    L = [f"EPISODE {n} — {title}", ""]
    for (t, k, spk, text, manner) in beats:
        L.append(tc(t))
        if k == S:
            L.append(text.upper())
        elif k == D:
            L.append(spk + (" (V.O.)" if manner == "V.O." else ""))
            if manner and manner != "V.O.":
                L.append(f"({manner})")
            L.append(text)
        else:
            L.append(text)
        L.append("")
    return "\n".join(L)


def render_docx(n, title, beats, path: Path):
    import docx
    d = docx.Document()
    d.add_heading(f"Episode {n} – {title}", level=1)
    for (t, k, spk, text, manner) in beats:
        if k == S:
            d.add_paragraph(f"{text} ({tc(t)})")
        elif k == D:
            m = f" ({manner})" if manner else ""
            d.add_paragraph(f"{tc(t)} {spk}{m}: {text}")
        else:
            d.add_paragraph(f"{tc(t)} {text}")
    d.save(str(path))


def render_pdf(eps: list[int], path: Path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    lines: list[str] = []
    for n in eps:
        title, beats = EPISODES[n]
        lines += [f"EPISODE {n} – {title}", ""]
        for (t, k, spk, text, manner) in beats:
            if k == S:
                lines.append(f"{text} [{tc(t)}]")
            elif k == D:
                m = f" ({manner})" if manner else ""
                lines.append(f"[{tc(t)}] {spk}{m}: {text}")
            else:
                lines.append(f"[{tc(t)}] {text}")
        lines.append("")
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    per_page = 38
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)]
    for pi, page in enumerate(pages, 1):
        c.setFont("Helvetica", 8)
        c.drawString(40, h - 30, f"{TITLE} — CONFIDENTIAL DRAFT")
        y = h - 60
        c.setFont("Helvetica", 9.5)
        for ln in page:
            # wrap long lines like a real PDF export would
            while len(ln) > 95:
                cut = ln.rfind(" ", 0, 95)
                c.drawString(40, y, ln[:cut])
                y -= 15
                ln = ln[cut + 1:]
            c.drawString(40, y, ln)
            y -= 15
        c.setFont("Helvetica", 8)
        c.drawString(w / 2 - 20, 25, f"Page {pi} of {len(pages)}")
        c.showPage()
    c.save()


MANUAL = """promo_id,segment,episode,start,end,hook,cliffhanger,notes
# Picked by hand by the repo author BEFORE running the tool, as an editor would. Lines starting with # are ignored.
M1,1,1,00:07,00:55,"Careful, maid — glasses shatter","You'll regret this / You're nothing","Humiliation set-up; pure ReelShort opener"
M2,1,1,00:36,00:49,"Wine thrown in her face","","Multi-segment: wine throw then the secret"
M2,2,1,01:12,01:35,"","Who's in there with you?","Secret reveal + someone at the door"
M3,1,2,00:35,01:22,"My engagement ring — it's gone","The cameras were broken. What a shame.","Framed by the fiancée"
M4,1,2,01:22,01:39,"Thrown out into the rain","","Cross-episode: thrown out -> heiress"
M4,2,3,00:00,00:13,"","Don't tell anyone. Not yet.",""
M5,1,3,00:33,01:01,"The thief came back for more","Ethan walks in","Lobby humiliation flips"
M6,1,4,01:06,01:43,"How dare you! — the slap","Every face turns to Ava","The best one. Post first."
M7,1,5,01:02,01:30,"It's me. Plan B. Tonight.","Who's there?","Threat + envelope + curtain moves"
M8,1,6,00:00,00:27,"Hooded figure grabs Ava by the throat","Her father set the fire?","Cold open attack"
M9,1,7,00:59,01:21,"You're eight weeks pregnant","Ava overhears","Pregnancy trope"
M10,1,8,00:59,01:27,"Open it. Prove you're the father.","The father is—","DNA cliffhanger"
"""


def main() -> int:
    if OUT.exists():
        for p in ("show", "sample_show.zip", "manual_promos_sample.csv"):
            q = OUT / p
            if q.is_dir():
                shutil.rmtree(q)
            elif q.exists():
                q.unlink()
    show = OUT / "show"
    more = show / "more"
    more.mkdir(parents=True, exist_ok=True)
    for n in (1, 2, 3):
        (show / f"Episode_{n:02d}.txt").write_text(render_bracket(n, *EPISODES[n]), encoding="utf-8")
    (more / "Ep04_table.txt").write_text(render_pipe(4, *EPISODES[4]), encoding="utf-8")
    render_docx(5, *EPISODES[5], more / "Ep05.docx")
    (more / "Episode 6 (classic).txt").write_text(render_classic(6, *EPISODES[6]), encoding="utf-8")
    render_pdf([7, 8], show / "Episodes_07-08.pdf")
    (OUT / "manual_promos_sample.csv").write_text(MANUAL, encoding="utf-8")
    # zip with a nested zip inside, plus macOS junk that must be ignored
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(show / "Episodes_07-08.pdf", "Episodes_07-08.pdf")
    with zipfile.ZipFile(OUT / "sample_show.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(show.rglob("*")):
            if f.is_file() and f.suffix != ".pdf":
                z.write(f, f"sample_show/{f.relative_to(show)}")
        z.writestr("sample_show/late_episodes.zip", inner.getvalue())
        z.writestr("__MACOSX/sample_show/._Episode_01.txt", b"junk")
        z.writestr("sample_show/.DS_Store", b"junk")
    print(f"Sample show written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
