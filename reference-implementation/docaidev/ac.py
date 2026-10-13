"""Pull acceptance criteria out of free text, so trackers without an AC field still work."""
import re

HEADING = re.compile(r"^\s{0,3}(#{1,6}\s*)?\**\s*(acceptance criteria|acceptance|definition of done)\s*:?\**\s*$", re.I)
ITEM = re.compile(r"^\s*(?:[-*+]\s+(?:\[[ xX]\]\s*)?|\d+[.)]\s+)(.+?)\s*$")
ANY_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+\S")


def extract_acceptance_criteria(text):
    """Return list items under an 'Acceptance criteria' heading; [] if none found."""
    if not text:
        return []
    lines = text.splitlines()
    out, active = [], False
    for line in lines:
        if HEADING.match(line):
            active = True
            continue
        if active:
            m = ITEM.match(line)
            if m:
                out.append(m.group(1))
            elif ANY_HEADING.match(line) or (line.strip() and out and not line.startswith((" ", "\t"))):
                break
    return out


def section_items(text, names):
    """Items (or prose lines) under the first heading matching one of `names`, e.g. ('steps',)."""
    if not text:
        return []
    want = {n.lower() for n in names}
    out, active = [], False
    for line in text.splitlines():
        m = re.match(r"^\s{0,3}#{1,6}\s*(.+?)\s*:?\s*$", line)
        if m:
            if active:
                break
            active = m.group(1).lower() in want
            continue
        if active and line.strip():
            im = ITEM.match(line)
            out.append(im.group(1) if im else line.strip())
    return out


TOPIC = re.compile(r"^\s{0,3}##\s+Topic:\s*(?P<kind>[A-Za-z ]+?)\s*:\s*(?P<title>.+?)\s*\((?P<scope>NEW|UPDATE)\)\s*$", re.I)
SUB = re.compile(r"^\s{0,3}###\s+(?P<name>.+?)\s*$")


def topics(text):
    """Parse '## Topic: KIND: Title (NEW|UPDATE)' blocks into
    [{kind, title, scope, sections: [(name, [lines])]}]. Sections start at '### Name'."""
    out, cur, sec = [], None, None
    for line in (text or "").splitlines():
        m = TOPIC.match(line)
        if m:
            cur = {"kind": m.group("kind").upper(), "title": m.group("title"), "scope": m.group("scope").upper(), "sections": []}
            out.append(cur); sec = None
            continue
        if cur is None:
            continue
        if re.match(r"^\s{0,3}##\s+\S", line):
            cur = sec = None
            continue
        s = SUB.match(line)
        if s:
            sec = (s.group("name"), [])
            cur["sections"].append(sec)
        elif sec is not None and line.strip():
            im = ITEM.match(line)
            sec[1].append(im.group(1) if im else line.strip())
    return out


def blocks(text, name):
    """Subsections under '## <name>' as [(sub heading, [lines])]; lines under no '###' use heading ''."""
    out, active, cur = [], False, None
    for line in (text or "").splitlines():
        m = re.match(r"^\s{0,3}##\s+(.+?)\s*$", line)
        if m and not line.lstrip().startswith("###"):
            active = m.group(1).strip().lower() == name.lower()
            cur = None
            continue
        if not active:
            continue
        s = SUB.match(line)
        if s:
            cur = (s.group("name"), [])
            out.append(cur)
        elif line.strip():
            if cur is None:
                cur = ("", [])
                out.append(cur)
            im = ITEM.match(line)
            cur[1].append(im.group(1) if im else line.strip())
    return out
