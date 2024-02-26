#!/usr/bin/env python3

from datetime import timedelta
import json
from typing import Any, Optional

import click
from iconsdk.builder.call_builder import CallBuilder

from .. import cui, service, util


@click.group("proposal")
def main():
    """
    Network Proposal related operations
    """
    pass


class Proposal(dict):
    StatusToStr = {
        0: "VOTING",
        1: "APPLIED",
        2: "DISAPPROVED",
        3: "CANCELED",
        4: "APPROVED",
        5: "EXPIRED",
    }

    def __new__(cls, *args: Any, **kwargs: Any) -> "Proposal":
        return super().__new__(cls, *args, **kwargs)

    @property
    def status(self) -> str:
        s = self.get("status")
        if s is None:
            return "UNKNOWN"
        return Proposal.StatusToStr[int(s, 0)]

    @property
    def agree_amount(self) -> int:
        return int(self["vote"]["agree"]["amount"], 0)

    @property
    def disagree_amount(self) -> int:
        return int(self["vote"]["disagree"]["amount"], 0)

    @property
    def novote_amount(self) -> int:
        return int(self["vote"]["noVote"]["amount"], 0)

    @property
    def vote_amount(self) -> int:
        return self.agree_amount + self.novote_amount + self.disagree_amount

    @staticmethod
    def count_votes(vote: dict) -> int:
        if "count" in vote:
            return int(vote["count"], 0)
        else:
            return len(vote["list"])

    @property
    def agree_count(self) -> int:
        return Proposal.count_votes(self["vote"]["agree"])

    @property
    def disagree_count(self) -> int:
        return Proposal.count_votes(self["vote"]["disagree"])

    @property
    def novote_count(self) -> int:
        return Proposal.count_votes(self["vote"]["noVote"])

    @property
    def vote_count(self) -> int:
        return self.agree_count + self.disagree_count + self.novote_count

    @property
    def agree_token_rate(self) -> float:
        return self.agree_amount / self.vote_amount

    @property
    def disagree_token_rate(self) -> float:
        return self.disagree_amount / self.vote_amount

    @property
    def novote_token_rate(self) -> float:
        return self.novote_amount / self.vote_amount

    @property
    def agree_count_rate(self) -> float:
        return self.agree_count / self.vote_count

    @property
    def disagree_count_rate(self) -> float:
        return self.disagree_count / self.vote_count

    @property
    def novote_count_rate(self) -> float:
        return self.novote_count / self.vote_count

    @property
    def end_block_height(self) -> int:
        return int(self["endBlockHeight"], 0)

    def get_remaining_time(self, height) -> timedelta:
        height_diff = self.end_block_height - height
        return timedelta(seconds=height_diff * 2) if height_diff >= 0 else timedelta()
    
    def get_content(self) -> list[dict]:
        ctype = self['contents']['type']
        if ctype == '0x9':
            return json.loads(self['contents']['value']['data'])

def summarize_content(c: dict) -> str:
    name = c['name']
    value = c['value']

    if name == 'networkScoreUpdate':
        value = { "address": value["address"], 'content': "..." }
    return f'{name} {json.dumps(value)}'



@main.command("list")
@click.option("--raw", is_flag=True)
@click.option('--all', '-a', is_flag=True)
def list_proposals(*, raw: bool = False, all: bool = False):
    svc = service.get_instance()
    info = svc.get_network_info()
    last_height = int(info["latest"], 0)

    ret = svc.call(CallBuilder(to=util.GOV_SCORE, method="getProposals").build())
    if raw:
        util.dump_json(ret)
    else:
        p = cui.MapPrinter(
            [
                cui.Header(lambda x: x["contents"]["title"], 60, "{:<60}", "Title"),
                cui.Row(lambda x: x["id"], 66, "{}", "ID"),
                cui.Row(lambda x: x.status, 20, "{}", "Status"),
                cui.Row(lambda x: x["proposerName"], 40, None, "Proposer"),
                cui.Row(
                    lambda x: (
                        x.agree_token_rate * 100,
                        x.disagree_token_rate * 100,
                        x.novote_token_rate * 100,
                    ),
                    60,
                    "Agree: {:6.2f}% / Disagree: {:6.2f}% / NoVoters: {:6.2f}%",
                    "Voter Token",
                ),
                cui.Row(
                    lambda x: (
                        x.agree_count_rate * 100,
                        x.disagree_count_rate * 100,
                        x.novote_count_rate*100,
                        x.novote_count,
                    ),
                    60,
                    "Agree: {:6.2f}% / Disagree: {:6.2f}% / NoVoters: {:6.2f}% ({:d} PReps)",
                    "Voter Count",
                ),
                cui.Row(
                    lambda x: x.get_remaining_time(last_height), 20, '{}', 'Expire'
                ),
            ]
        )
        proposals: list[Proposal] = map(lambda x: Proposal(x), ret['proposals'])
        if not all:
            proposals = filter(lambda x: x.end_block_height>last_height, proposals) 
        p.print_separater()
        for proposal in proposals:
            p.print_data(proposal)
        p.print_separater()


@main.command("get")
@click.option("--raw", is_flag=True)
@click.option("--name", is_flag=True)
@click.argument("id")
def get_proposal(id: str, *, raw=False, name=False):
    svc = service.get_instance()
    info = svc.get_network_info()
    last_height = int(info["latest"], 0)

    response = svc.call(
        CallBuilder(
            to=util.GOV_SCORE,
            method="getProposal",
            params={"id": id},
        ).build()
    )
    if raw:
        util.dump_json(response)
    else:
        proposal = Proposal(response)
        rows = [
            cui.Header(lambda x: x["contents"]["title"], 0, "{:<}", "Title"),
            cui.Row(lambda x: x["id"], 66, "{}", "ID"),
            cui.Row(lambda x: x.status, 20, "{}", "Status"),
            cui.Row(lambda x: x["proposerName"], 40, None, "Proposer"),
            cui.Row(
                lambda x: (
                    x.agree_token_rate * 100,
                    x.disagree_token_rate * 100,
                    x.novote_token_rate * 100,
                ),
                60,
                "Agree: {:6.2f}% / Disagree: {:6.2f}% / NoVoters: {:6.2f}%",
                "Voter Token",
            ),
            cui.Row(
                lambda x: (
                    x.agree_count_rate * 100,
                    x.disagree_count_rate * 100,
                    x.novote_count_rate*100,
                    x.novote_count,
                ),
                60,
                "Agree: {:6.2f}% / Disagree: {:6.2f}% / NoVoters: {:6.2f}% ({:d} PReps)",
                "Voter Count",
            ),
            cui.Row(lambda x: x.get_remaining_time(last_height), 20, "{}", "Expire"),
            cui.Row(
                lambda x: x['contents']['description'], 60, None, 'Description'
            ),
        ]

        contents: list[dict] = proposal.get_content()
        idx = 1
        for c in contents:
            rows.append(cui.Row(summarize_content(c), 60, None, f'Content[{idx}]'))
            idx += 1

        apply: Optional[dict] = proposal.get("apply")
        if apply is not None:
            rows.append(cui.Header("Apply", 0))
            rows += [
                cui.Row(apply["name"], 40, "{}", "Applyer"),
                cui.Row(apply["id"], 66, "{}", "TXHash"),
                cui.Row(util.datetime_from_ts(apply["timestamp"]), 30, "{}", "When"),
            ]

        novoters: list[dict] = proposal["vote"]["noVote"]["list"]
        if len(novoters) > 0:
            rows.append(cui.Header("No Voters", 0))
            idx = 0
            for novoter in novoters:
                name = novoter
                try:
                    prep = svc.call(
                        CallBuilder(
                            to=util.CHAIN_SCORE,
                            method="getPRep",
                            params={"address": novoter},
                        ).build()
                    )
                    name = f'{novoter} {prep["name"]:20.20}'
                except:
                    raise
                rows.append(cui.Row(name, 63, None, f"NoVoter[{idx+1}]"))
                idx += 1


        p = cui.MapPrinter(rows)
        p.print_data(proposal, underline=True)
