"""Relationship, courtship, language and exchange systems."""
from __future__ import annotations

import itertools
import random
import zlib
from typing import Any

from .agent import Agent, Relationship
from .constants import LANGUAGE_CONCEPTS
from .culture import Language, borrow_words, coin_word, create_language
from .economy import surplus_offer, wanted_item


def _pair_priority(engine: Any, a: Agent, b: Agent) -> float:
    """Rank which pairs deserve one of the few daily encounters.

    Existing bonds and unresolved disputes matter more than two strangers
    brushing past each other; unmet social need creates urgency.
    """
    rel = a.relationships.get(b.id)
    score = 4.0
    if rel is None:
        score += 6.0
    else:
        score += min(9.0, abs(rel.affinity) * 0.1)
        score += min(4.0, rel.interactions * 0.3)
        if rel.affinity < -20:
            score += 3.0
    score += max(0.0, 100.0 - a.needs.get("social", 100)) * 0.04
    score += max(0.0, 100.0 - b.needs.get("social", 100)) * 0.04
    score -= engine.distance(a.position[0], a.position[1], b.position[0], b.position[1]) * 0.4
    return score


class SocialMixin:
    # --------------------------------------------------------------- phase
    def _social_phase(self) -> None:
        by_tile: dict[tuple[int, int], list[Agent]] = {}
        for agent in self.alive_agents():
            by_tile.setdefault((agent.position[0], agent.position[1]), []).append(agent)
        for position, group in by_tile.items():
            if len(group) < 2:
                continue
            group.sort(key=lambda a: a.id)
            # At most two meaningful encounters per tile per day; larger crowds
            # are not an excuse for 400 conversations.
            pairs = list(itertools.combinations(group, 2))
            pairs.sort(key=lambda pair: -_pair_priority(self, pair[0], pair[1]))
            used: set[str] = set()
            for a, b in pairs:
                if len(used) >= 2:
                    break
                if a.id in used or b.id in used:
                    continue
                if a.last_social_action_day == self.day or b.last_social_action_day == self.day:
                    continue
                if not a.alive or not b.alive:
                    continue
                rel_ab = a.relationships.get(b.id)
                if rel_ab and rel_ab.affinity < -45 and a.personality["aggressiveness"] < 0.65:
                    continue
                used.add(a.id)
                used.add(b.id)
                self._choose_social_action(a, b)

    def _choose_social_action(self, a: Agent, b: Agent) -> None:
        rng = random.Random(zlib.crc32(f"social:{a.id}:{b.id}:{self.day}".encode()))
        rel = a.relationships.get(b.id)
        if rel and rel.affinity < -25:
            if a.personality["aggressiveness"] > 0.55 and rng.random() < 0.3:
                self._conflict(a, b, lethal_intent=False)
            else:
                a.needs["social"] = max(0.0, a.needs["social"] - 2)
                b.needs["social"] = max(0.0, b.needs["social"] - 2)
                self._memory(a, "conflict", f"Avoided {b.name} after an earlier dispute.", 0.2, -0.2, participants=[b.id], tags=["conflict"])
            return
        # Feed someone who is in trouble, if empathy and surplus allow it.
        if (b.needs["hunger"] < 32 and a.inventory.get("food", 0) > 2.5 and a.personality["empathy"] > 0.5):
            amount = min(1.5, a.inventory["food"] - 1.0)
            if amount > 0:
                a.inventory["food"] = round(a.inventory["food"] - amount, 2)
                b.add_item("food", amount)
                b.needs["hunger"] = min(100, b.needs["hunger"] + 24)
                self._record_gift(a, b, amount)
                self._interact(a, b, strong=True, context="help")
                return
        # Barter emerges when both sides have a real surplus and a real need.
        if rng.random() < 0.18 and self._can_barter(a, b) and self.distance(a.position[0], a.position[1], b.position[0], b.position[1]) <= 2:
            self._execute_barter(a, b)
            a.last_social_action_day = self.day
            b.last_social_action_day = self.day
            return
        self._interact(a, b, strong=rng.random() < 0.55, context="talk")

    # ---------------------------------------------------------- interaction
    def _ensure_language(self, a: Agent, b: Agent) -> tuple[Language | None, str]:
        lang_a = next((self.languages[lid] for lid in a.known_languages if lid in self.languages), None)
        lang_b = next((self.languages[lid] for lid in b.known_languages if lid in self.languages), None)
        if lang_a is None and lang_b is None:
            seed_int = zlib.crc32(f"lang:{self.seed}:{a.origin_group}:{a.id}".encode())
            language = create_language(seed_int, settlement_id="", day=self.day)
            keep = sorted(language.lexicon)[:10]
            language.lexicon = {k: language.lexicon[k] for k in keep}
            language.name = f"{language.name} Pidgin"
            language.speakers = 2
            language.origins = [f"first exchanges between {a.name} and {b.name}"]
            self.languages[language.id] = language
            for person in (a, b):
                person.known_languages.append(language.id)
                person.personal_vocabulary.update(language.lexicon)
                self._memory(person, "social", f"Began shaping a shared speech with {b.name if person is a else a.name}.", 0.6, 0.4,
                             participants=[b.id if person is a else a.id], tags=["language", "cooperation"])
            self.add_event(
                "culture", "A shared speech begins to form",
                f"Repeated exchanges between {a.name} and {b.name} produced a small common vocabulary of {len(language.lexicon)} grounded words.",
                importance=3, participants=[a.id, b.id], location=list(a.position),
                related={"language_id": language.id, "words": len(language.lexicon)},
            )
            return language, "new"
        if lang_a and lang_b and lang_a.id != lang_b.id:
            # Contact borrows words in the direction with more prestige/trust.
            if a.relationships.get(b.id) and a.relationships[b.id].affinity >= 0:
                loans = borrow_words(lang_b, lang_a, random.Random(zlib.crc32(f"loan:{a.id}:{b.id}:{self.day}".encode())), self.day, amount=1)
                for loan in loans:
                    a.personal_vocabulary[loan["concept"]] = loan["word"]
                a.known_languages.append(lang_b.id) if lang_b.id not in a.known_languages else None
                return lang_a, f"borrowed:{loans[0]['concept']}" if loans else "different"
            return lang_a, "different"
        if lang_a and not lang_b:
            b.known_languages.append(lang_a.id)
            b.personal_vocabulary.update(lang_a.lexicon)
            self._memory(b, "social", f"Learned some of {a.name}'s words.", 0.4, 0.3, participants=[a.id], tags=["language"])
            return lang_a, "learned"
        if lang_b and not lang_a:
            a.known_languages.append(lang_b.id)
            a.personal_vocabulary.update(lang_b.lexicon)
            self._memory(a, "social", f"Learned some of {b.name}'s words.", 0.4, 0.3, participants=[b.id], tags=["language"])
            return lang_b, "learned"
        return lang_a or lang_b, "same"

    def _converse(self, a: Agent, b: Agent, language: Language | None, context: str) -> str:
        if not language:
            return ""
        topics: list[str] = []
        if context == "help" or b.needs["hunger"] < 40:
            topics += ["food", "thanks"]
        if b.needs["thirst"] < 40:
            topics += ["water"]
        if context == "family":
            topics += ["together", "friend", "home"]
        if a.relationships.get(b.id) and (a.relationships[b.id].affinity > 35):
            topics += ["friend", "good"]
        if context == "trade":
            topics += ["trade", "gift", "many"]
        if self.world.active_disaster:
            topics += ["danger", "bad"]
        if not topics:
            topics = ["welcome", "friend", "good"]
        topics = [t for t in dict.fromkeys(topics) if t in language.lexicon][:3]
        words = [language.lexicon[t] for t in topics]
        phrase = " ".join(words)
        gloss = ", ".join(topics)
        a.stats["last_speech"] = {"language": language.name, "phrase": phrase, "gloss": gloss, "to": b.id, "day": self.day}
        b.stats["last_heard"] = {"language": language.name, "phrase": phrase, "gloss": gloss, "from": a.id, "day": self.day}
        return f'“{phrase}” ({gloss})'

    def _interact(self, a: Agent, b: Agent, strong: bool = False, context: str = "talk") -> None:
        if not a.alive or not b.alive:
            return
        if a.last_social_action_day == self.day and b.last_social_action_day == self.day:
            return
        a.last_social_action_day = self.day
        b.last_social_action_day = self.day
        rel_ab = a.relation(b.id, self.day)
        rel_ba = b.relation(a.id, self.day)
        first = rel_ab.interactions == 0 and rel_ba.interactions == 0
        language, language_status = self._ensure_language(a, b)
        speech = self._converse(a, b, language, context)
        affinity_gain = (2.2 if strong else 1.0) + a.personality["sociability"] * 2.0 + b.personality["sociability"] * 1.2
        if context == "help":
            affinity_gain += 4
        if context == "family":
            affinity_gain += 3
        trust_gain = 0.8 + a.personality["honesty"] * 1.5 + b.personality["honesty"] * 0.8
        for rel in (rel_ab, rel_ba):
            rel.interactions += 1
            rel.last_interaction_day = self.day
            rel.affinity = round(max(-100, min(100, rel.affinity + affinity_gain + random.Random(zlib.crc32(f"aff:{a.id}:{b.id}:{self.day}".encode())).uniform(-0.5, 0.7))), 2)
            rel.trust = round(max(-100, min(100, rel.trust + trust_gain)), 2)
            rel.add_history(self.day, f"Conversation ({context})", 0.3)
        previous_type = rel_ab.type
        rel_ab.update_type(partnered=a.partner_id == b.id)
        rel_ba.update_type(partnered=b.partner_id == a.id)
        social_gain = 26 if strong else 12
        a.needs["social"] = min(100, a.needs["social"] + social_gain)
        b.needs["social"] = min(100, b.needs["social"] + social_gain * 0.8)
        a.needs["safety"] = min(100, a.needs["safety"] + 1.5)
        b.needs["safety"] = min(100, b.needs["safety"] + 1.5)
        summary = f"Spoke with {b.name}" + (f" {speech}" if speech else "") + "."
        if first:
            summary = f"Met {b.name} for the first time. " + (speech or "")
            a.reputation = min(100, a.reputation + 0.2)
            b.reputation = min(100, b.reputation + 0.2)
            self._memory(a, "social", summary, 0.45, 0.25, participants=[b.id], tags=["meeting", "social"], location=list(a.position))
            self._memory(b, "social", f"Met {a.name} for the first time. " + (speech or ""), 0.45, 0.25, participants=[a.id], tags=["meeting", "social"], location=list(b.position))
            if a.settlement_id and a.settlement_id == b.settlement_id:
                self._memory(a, "social", f"Recognized {b.name} as a fellow resident of {self._settlement_of(a).name}.", 0.25, 0.2, participants=[b.id], tags=["settlement", "social"])
        else:
            self._memory(a, "social", summary, 0.22, 0.2, participants=[b.id], tags=["conversation", "social"], location=list(a.position))
            self._memory(b, "social", f"Spoke with {a.name}.", 0.2, 0.15, participants=[a.id], tags=["conversation", "social"], location=list(b.position))
        # A friendship is a real threshold crossing, not a cosmetic label.
        if previous_type != rel_ab.type and rel_ab.type in ("friend", "close_friend"):
            self.add_event(
                "social", f"{a.name} and {b.name} become {rel_ab.type.replace('_', ' ')}s",
                f"After {rel_ab.interactions} interactions, trust between {a.name} and {b.name} reached {rel_ab.trust:.0f} and affection reached {rel_ab.affinity:.0f}.",
                importance=2, participants=[a.id, b.id], location=list(a.position),
                related={"relationship": rel_ab.type},
            )
            self._memory(a, "social", f"Came to trust {b.name} as a {rel_ab.type.replace('_', ' ')}.", 0.6, 0.6, participants=[b.id], tags=["friendship"])
            self._memory(b, "social", f"Came to trust {a.name} as a {rel_ab.type.replace('_', ' ')}.", 0.6, 0.6, participants=[a.id], tags=["friendship"])
        # Teaching passes skills, slowly and imperfectly.
        rng = random.Random(zlib.crc32(f"teach:{a.id}:{b.id}:{self.day}".encode()))
        if rng.random() < 0.35:
            known = {s for s in a.skills if a.skills[s] > 0.3}
            if known:
                skill = max(known, key=lambda s: a.skills[s])
                if b.skills.get(skill, 0) < a.skills[skill] - 0.08:
                    gain = min(0.03, (a.skills[skill] - b.skills[skill]) * 0.12)
                    b.gain_skill(skill, gain)
                    b.stats["learned_from"] = {"skill": skill, "from": a.name, "day": self.day}
        if language_status.startswith("borrowed"):
            self._memory(a, "social", f"Adopted a word from {b.name}'s speech.", 0.3, 0.2, participants=[b.id], tags=["language"])
        if a.partner_id == b.id:
            rel_ab.affinity = min(100, rel_ab.affinity + 1.5)
            rel_ba.affinity = min(100, rel_ba.affinity + 1.5)
            a.needs["social"] = min(100, a.needs["social"] + 10)
            b.needs["social"] = min(100, b.needs["social"] + 10)
            if a.pregnant:
                b.needs["shelter"] = min(100, b.needs["shelter"] + 2)

    # ------------------------------------------------------------- exchange
    def _can_barter(self, a: Agent, b: Agent) -> bool:
        a_offer = surplus_offer(a)
        b_offer = surplus_offer(b)
        a_want = wanted_item(a)
        b_want = wanted_item(b)
        return bool(a_offer and b_offer and a_want and b_want and (a_offer == b_want or b_offer == a_want or a_want != a_offer))

    def _execute_barter(self, a: Agent, b: Agent) -> bool:
        if not a.alive or not b.alive:
            return False
        offer = surplus_offer(a)
        want = wanted_item(a)
        other_offer = surplus_offer(b)
        other_want = wanted_item(b)
        if not offer or not want:
            return False
        # The counterpart must have what we want, or want what we offer.
        if other_offer != want and other_want != offer and other_want is None:
            return False
        a_amount = 1.0
        b_amount = 1.0
        if a.inventory.get(offer, 0) < 1.1 or (other_offer and b.inventory.get(other_offer, 0) < 1.1):
            return False
        # Trade only if both sides feel the exchange is not insulting.
        from .economy import agent_valuation
        a_value = agent_valuation(a, want) if want else 1.0
        b_value = agent_valuation(b, offer) if offer else 1.0
        if not (0.35 <= a_value / max(0.2, b_value) <= 3.0):
            return False
        a.inventory[offer] = round(a.inventory[offer] - a_amount, 2)
        b.inventory[offer] = round(b.inventory.get(offer, 0) + a_amount, 2)
        if other_offer:
            b.inventory[other_offer] = round(b.inventory[other_offer] - b_amount, 2)
            a.inventory[other_offer] = round(a.inventory.get(other_offer, 0) + b_amount, 2)
        rel_ab = a.relation(b.id, self.day)
        rel_ba = b.relation(a.id, self.day)
        for rel in (rel_ab, rel_ba):
            rel.trades += 1
            rel.trust = round(min(100, rel.trust + 2.5), 2)
            rel.affinity = round(min(100, rel.affinity + 2.0), 2)
            rel.add_history(self.day, f"Traded {offer} for {other_offer or want}", 0.4)
            rel.update_type()
        self.trades += 1
        settlement = self._settlement_of(a)
        items = {offer: a_amount}
        if other_offer:
            items[other_offer] = b_amount
        self._record_trade(a.id, b.id, "barter", items, 0.0, settlement)
        a.state = f"Traded {offer} with {b.name}"
        b.state = f"Traded with {a.name}"
        self._memory(a, "trade", f"Traded {a_amount:.1f} {offer} to {b.name} for {b_amount:.1f} {other_offer or want}.", 0.35, 0.3, participants=[b.id], tags=["trade"])
        self._memory(b, "trade", f"Traded {b_amount:.1f} {other_offer or want} to {a.name} for {a_amount:.1f} {offer}.", 0.35, 0.3, participants=[a.id], tags=["trade"])
        a.last_social_action_day = self.day
        b.last_social_action_day = self.day
        if rel_ab.trades == 1:
            self.add_event(
                "economy", f"First exchange between {a.name} and {b.name}",
                f"{a.name} exchanged {a_amount:.1f} {offer} with {b.name} for {b_amount:.1f} {other_offer or want}. "
                "Both parties judged the exchange fair enough to accept.",
                importance=2, participants=[a.id, b.id], location=list(a.position),
                related={"barter": True},
            )
        return True

    def _record_trade(self, buyer_id: str, seller_id: str, kind: str, items: dict[str, float], currency: float, settlement: Any) -> None:
        self.counters["transaction"] = self.counters.get("transaction", 0) + 1
        tx = {
            "id": f"tx_{self.counters['transaction']:06d}",
            "day": self.day,
            "kind": kind,
            "buyer_id": buyer_id,
            "buyer_name": self.agents[buyer_id].name if buyer_id in self.agents else (settlement.name if settlement and buyer_id == settlement.id else "Unknown"),
            "seller_id": seller_id,
            "seller_name": self.agents[seller_id].name if seller_id in self.agents else (settlement.name if settlement and seller_id == settlement.id else "Unknown"),
            "items": items,
            "currency": round(currency, 2),
            "settlement_id": settlement.id if settlement else None,
            "settlement_name": settlement.name if settlement else None,
        }
        self.recent_transactions.append(tx)
        if len(self.recent_transactions) > 600:
            self.recent_transactions = self.recent_transactions[-600:]
        if settlement:
            settlement.trade_volume = round(settlement.trade_volume + sum(items.values()) + currency * 0.5, 1)

    def _record_gift(self, giver: Agent, receiver: Agent, amount: float) -> None:
        rel_g = giver.relation(receiver.id, self.day)
        rel_r = receiver.relation(giver.id, self.day)
        rel_g.gifts += 1
        rel_r.gifts += 1
        rel_g.affinity = round(min(100, rel_g.affinity + 5), 2)
        rel_r.affinity = round(min(100, rel_r.affinity + 7), 2)
        rel_g.trust = round(min(100, rel_g.trust + 3), 2)
        rel_r.trust = round(min(100, rel_r.trust + 5), 2)
        rel_g.add_history(self.day, f"Gave food to {receiver.name}", 0.8)
        rel_r.add_history(self.day, f"Received food from {giver.name}", 1.0)
        rel_g.update_type()
        rel_r.update_type()
        giver.reputation = min(100, giver.reputation + 0.8)
        giver.influence = min(100, giver.influence + 0.15)
        self._memory(giver, "help", f"Shared {amount:.1f} food with {receiver.name}.", 0.5, 0.6, participants=[receiver.id], tags=["help", "gift"])
        self._memory(receiver, "help", f"{giver.name} gave them {amount:.1f} food when it was needed.", 0.75, 0.85, participants=[giver.id], tags=["help", "gift"])
        receiver.needs["safety"] = min(100, receiver.needs["safety"] + 4)
        if rel_r.gifts == 1:
            self.add_event(
                "social", f"{giver.name} helps {receiver.name}",
                f"{giver.name} shared {amount:.1f} food with {receiver.name}. This is remembered.",
                importance=2, participants=[giver.id, receiver.id], location=list(giver.position),
                related={"gift": amount},
            )

    # ------------------------------------------------------------- courtship
    def _court(self, a: Agent, b: Agent) -> None:
        if not a.is_adult or not b.is_adult or a.partner_id or b.partner_id:
            self._interact(a, b, strong=True, context="talk")
            return
        self._interact(a, b, strong=True, context="family")
        rel = a.relation(b.id, self.day)
        rel.affinity = round(min(100, rel.affinity + 5), 2)
        other = b.relation(a.id, self.day)
        other.affinity = round(min(100, other.affinity + 4), 2)
        rng = random.Random(zlib.crc32(f"court:{a.id}:{b.id}:{self.day}".encode()))
        # A partnership should grow out of repeated courtship, not require a
        # near-maxed prior friendship. At +5/+4 affinity per courtship these
        # thresholds are reached in a handful of meetings.
        if rel.affinity > 14 and other.affinity > 10 and rng.random() < 0.3 + a.personality["sociability"] * 0.4:
            self._form_partnership(a, b)
        else:
            self._memory(a, "family", f"Spent time with {b.name} and felt closer.", 0.35, 0.5, participants=[b.id], tags=["courtship"])
            self._memory(b, "family", f"Spent time with {a.name}.", 0.3, 0.45, participants=[a.id], tags=["courtship"])

    def _form_partnership(self, a: Agent, b: Agent) -> None:
        if a.partner_id or b.partner_id or not a.is_adult or not b.is_adult:
            return
        a.partner_id = b.id
        b.partner_id = a.id
        rel_ab = a.relation(b.id, self.day)
        rel_ba = b.relation(a.id, self.day)
        for rel in (rel_ab, rel_ba):
            rel.affinity = round(min(100, rel.affinity + 18), 2)
            rel.trust = round(min(100, rel.trust + 10), 2)
            rel.type = "partner"
            rel.add_history(self.day, "Became partners", 1.0)
        family = self.families.get(a.family_id or "") or self.families.get(b.family_id or "")
        if family is None:
            name_rng = random.Random(zlib.crc32(f"family:{a.id}:{b.id}".encode()))
            from .names import family_name
            family = {
                "id": self._next_family_id(),
                "name": f"House {family_name(name_rng)}",
                "created_day": self.day,
                "partner_ids": [a.id, b.id],
                "member_ids": [a.id, b.id],
                "children": [],
                "home_settlement_id": a.settlement_id or b.settlement_id,
            }
            self.families[family["id"]] = family
        else:
            for person in (a, b):
                if person.id not in family["member_ids"]:
                    family["member_ids"].append(person.id)
            family["partner_ids"] = list(dict.fromkeys(family.get("partner_ids", []) + [a.id, b.id]))
        for person in (a, b):
            person.family_id = family["id"]
            person.needs["social"] = min(100, person.needs["social"] + 25)
            person.current_goal["progress"] = round(person.current_goal.get("progress", 0) + 0.05, 3)
        self._memory(a, "family", f"Became partners with {b.name}.", 0.95, 0.95, participants=[b.id], tags=["family", "partnership"])
        self._memory(b, "family", f"Became partners with {a.name}.", 0.95, 0.95, participants=[a.id], tags=["family", "partnership"])
        settlement = self._settlement_of(a)
        self.add_event(
            "social", f"{a.name} and {b.name} become partners",
            f"{a.name} ({a.age}) and {b.name} ({b.age}) formalized their bond in {settlement.name if settlement else 'the open country'}. "
            f"Their household is now recorded as {family['name']}.",
            importance=4, participants=[a.id, b.id], location=list(a.position),
            location_name=settlement.name if settlement else None,
            related={"family_id": family["id"], "family_name": family["name"]},
        )
        if settlement:
            self._culture_from_event(settlement, "partnership", couple=[a, b])

    # -------------------------------------------------------------- conflict
    def _conflict(self, a: Agent, b: Agent, lethal_intent: bool = False) -> None:
        if not a.alive or not b.alive:
            return
        rng = random.Random(zlib.crc32(f"conflict:{a.id}:{b.id}:{self.day}".encode()))
        a_power = a.personality["aggressiveness"] * 0.6 + a.skills.get("hunting", 0) * 0.3 + (0.2 if a.inventory.get("tools", 0) else 0)
        b_power = b.personality["aggressiveness"] * 0.6 + b.skills.get("hunting", 0) * 0.3 + (0.2 if b.inventory.get("tools", 0) else 0)
        damage_a = rng.uniform(4, 13) * (1.0 + max(0.0, b_power - a_power))
        damage_b = rng.uniform(4, 13) * (1.0 + max(0.0, a_power - b_power))
        if lethal_intent:
            damage_a *= 1.5
            damage_b *= 1.5
        a.needs["health"] = max(0.0, a.needs["health"] - damage_a)
        b.needs["health"] = max(0.0, b.needs["health"] - damage_b)
        a.needs["safety"] = max(0.0, a.needs["safety"] - 22)
        b.needs["safety"] = max(0.0, b.needs["safety"] - 22)
        a.needs["energy"] = max(0.0, a.needs["energy"] - 8)
        b.needs["energy"] = max(0.0, b.needs["energy"] - 8)
        rel_ab = a.relation(b.id, self.day)
        rel_ba = b.relation(a.id, self.day)
        for rel, other in ((rel_ab, b), (rel_ba, a)):
            rel.affinity = round(max(-100, rel.affinity - 28), 2)
            rel.trust = round(max(-100, rel.trust - 35), 2)
            rel.conflicts += 1
            rel.type = "enemy"
            rel.add_history(self.day, f"Fought with {other.name}", -1.0)
        self.conflicts += 1
        a.reputation = max(0.0, a.reputation - 5)
        b.reputation = max(0.0, b.reputation - 3)
        a.state = f"Fighting with {b.name}"
        b.state = f"Fighting with {a.name}"
        self._memory(a, "conflict", f"Fought with {b.name}; both were hurt.", 0.8, -0.8, participants=[b.id], tags=["conflict", "violence"])
        self._memory(b, "conflict", f"Fought with {a.name}; both were hurt.", 0.85, -0.85, participants=[a.id], tags=["conflict", "violence"])
        severity = "gravely" if min(a.needs["health"], b.needs["health"]) < 30 else "painfully"
        self.add_event(
            "conflict", f"Violence between {a.name} and {b.name}",
            f"A dispute turned violent. Both were {severity} hurt; their relationship is now hostile. "
            f"{a.name} has health {a.needs['health']:.0f}, {b.name} {b.needs['health']:.0f}.",
            importance=4 if min(a.needs["health"], b.needs["health"]) < 30 else 3,
            participants=[a.id, b.id], location=list(a.position),
            consequences=["Relationship became enmity", "Health and safety reduced"],
            related={"conflict": True},
        )
        if a.personality["honesty"] < 0.4:
            settlement = self._settlement_of(a)
            if settlement:
                settlement.stats["theft"] = self.day
