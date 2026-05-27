"""Tests do render de markdown leve (CP-B4): bold, listas, quebras, escape."""

from __future__ import annotations

from src.utils.markdown_leve import render_md_leve


def test_bold():
    assert "<strong>Precisão</strong>" in str(render_md_leve("O gargalo é **Precisão**."))


def test_lista():
    out = str(render_md_leve("- um\n- dois"))
    assert "<ul" in out and out.count("<li>") == 2 and "um" in out


def test_paragrafos_e_quebra():
    out = str(render_md_leve("linha 1\nlinha 2\n\npar 2"))
    assert out.count("<p>") == 2 and "<br>" in out


def test_escapa_html():
    out = str(render_md_leve('cliente disse "<script>" & cia'))
    assert "<script>" not in out and "&lt;script&gt;" in out and "&amp;" in out


def test_vazio():
    assert str(render_md_leve("")) == ""
