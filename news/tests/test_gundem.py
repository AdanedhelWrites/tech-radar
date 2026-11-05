"""Gundem gruplama ve puan testleri (news/gundem.py).

Gercek veri: fixtures/gundem_basliklari.json, canli veritabanindan yalniz okunarak aktarildi
(bes bolum; 09-28..10-03, 10-18..10-23, 10-27..11-03; yalniz halka acik haber basliklari).
`simdi` Istanbul saatiyle verilir (spec s5).
"""
import json
import random
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from news import gundem
from news.gundem import Ogeler, olay_puani, olaylari_grupla, olaylari_sec, penceredeki, temsilci

IST = ZoneInfo('Europe/Istanbul')
FIKSTUR = Path(__file__).resolve().parent / 'fixtures' / 'gundem_basliklari.json'


@lru_cache(maxsize=1)
def fikstur():
    with open(FIKSTUR, encoding='utf-8') as f:
        satirlar = json.load(f)
    return tuple(
        Ogeler(
            bolum=s['bolum'],
            id=s['id'],
            source=s['source'],
            baslik=s['original_title'],
            created_at=datetime.fromisoformat(s['created_at'].replace('Z', '+00:00')),
            yayin=date.fromisoformat(s['yayin']) if s['yayin'] else None,
            ceviri=s['translation_provider'],
            tr_baslik=s['turkish_title'],
        )
        for s in satirlar
    )


def ist(metin):
    return datetime.fromisoformat(metin).replace(tzinfo=IST)


def oge(id, source, baslik, created_at, bolum='news', yayin=None, ceviri='gemini', tr_baslik='Baslik'):
    return Ogeler(bolum=bolum, id=id, source=source, baslik=baslik, created_at=created_at,
                  yayin=yayin, ceviri=ceviri, tr_baslik=tr_baslik)


def secilen_olaylar(ogeler, simdi, adet=6):
    """olaylari_sec'in sectigi satirlarin olaylari (secim aninda birlestirme sonrasi)."""
    sirali = sorted(penceredeki(list(ogeler), simdi), key=lambda o: (o.bolum, o.id))
    ozellik_listesi = gundem._baslik_ozellikleri(sirali)
    ozellik = {(o.bolum, o.id): oz for o, oz in zip(sirali, ozellik_listesi)}
    satirlar, _ = gundem._secip_birlestir(gundem._grupla(sirali, ozellik_listesi), simdi, adet, ozellik)
    return [olay for olay, _, _ in satirlar]


def olay_of(olaylar, bolum, id):
    for i, olay in enumerate(olaylar):
        if any(o.bolum == bolum and o.id == id for o in olay):
            return i
    raise AssertionError(f'{bolum}/{id} pencerede yok')


class GercekVeriOrnekleriTest(SimpleTestCase):
    """spec s5 kabul ornekleri."""

    def test_binance_30_ekim_birinci(self):
        secim = olaylari_sec(list(fikstur()), ist('2026-10-30 20:00'))
        self.assertEqual(len(secim), 6)
        self.assertIn('Binance', secim[0]['temsilci'].baslik)
        self.assertGreaterEqual(secim[0]['kaynak_sayisi'], 5)
        binance_satirlari = [s for s in secim if 'Binance' in s['temsilci'].baslik]
        self.assertEqual(len(binance_satirlari), 1)

    def test_binance_2_kasim_ilk_uc_ve_tek_satir(self):
        simdi = ist('2026-11-02 12:00')
        secim = olaylari_sec(list(fikstur()), simdi)
        self.assertTrue(any('Binance' in s['temsilci'].baslik for s in secim[:3]))
        self.assertEqual(sum(1 for s in secim if 'Binance' in s['temsilci'].baslik), 1)
        # FBI / Kuzey Kore haberleri ayni olayda: penceredeki tum Binance basliklari tek olay.
        olaylar = olaylari_grupla(penceredeki(list(fikstur()), simdi))
        binance = {olay_of(olaylar, o.bolum, o.id) for olay in olaylar for o in olay if 'Binance' in o.baslik}
        self.assertEqual(len(binance), 1)
        olay = olaylar[binance.pop()]
        self.assertTrue(any('FBI' in o.baslik and 'North Korea' in o.baslik for o in olay))

    def test_php2shell_21_ekim_birinci(self):
        secim = olaylari_sec(list(fikstur()), ist('2026-10-21 20:00'))
        self.assertIn('PHP', secim[0]['temsilci'].baslik)
        self.assertGreaterEqual(secim[0]['kaynak_sayisi'], 6)
        self.assertEqual(sum(1 for s in secim if 'PHP' in s['temsilci'].baslik), 1)

    def test_gemini_argon_ilk_uc_bolumler_arasi(self):
        secim = olaylari_sec(list(fikstur()), ist('2026-10-01 20:00'))
        argon = [s for s in secim[:3] if 'Argon' in s['temsilci'].baslik]
        self.assertEqual(len(argon), 1)
        self.assertLessEqual({'ai', 'news'}, set(argon[0]['bolumler']))
        self.assertEqual(sum(1 for s in secim if 'Argon' in s['temsilci'].baslik), 1)

    def test_genel_ad_tek_basina_birlestirmez(self):
        simdi = ist('2026-10-29 20:00')
        olaylar = olaylari_grupla(penceredeki(list(fikstur()), simdi))
        # "Microsoft urges Entra ID admins to migrate users to passkeys" (Bleeping Computer)
        # "Researcher Reveals How Logic Bugs Alone Cracked Microsoft Edge in $175,000 Pwn2Own Win" (THN)
        self.assertNotEqual(olay_of(olaylar, 'news', 1907), olay_of(olaylar, 'news', 1931))
        # "Meet Google DeepMind's Genie 4: Real-Time World Model With Native Audio" (MarkTechPost)
        # "Google announces Gemini 4 Carbon, its latest frontier AI model that you can't use" (Ars)
        self.assertNotEqual(olay_of(olaylar, 'ai', 1710), olay_of(olaylar, 'ai', 1736))
        # Karsit kontrol: ayni olay olan cift birlesir (Microsoft Authenticator acigi; HNS + THN).
        self.assertEqual(olay_of(olaylar, 'news', 1829), olay_of(olaylar, 'news', 1834))
        self.assertEqual(olay_of(olaylar, 'ai', 1718), olay_of(olaylar, 'ai', 1736))


class TaramaCapalariTest(SimpleTestCase):
    """Inceleme taramasinin (15 dk aralik) buldugu karsi hedef ihlallerinin capalari (spec s4)."""

    def satir_sayisi(self, simdi, sozcuk):
        return sum(
            1 for olay in secilen_olaylar(fikstur(), simdi)
            if any(sozcuk in o.baslik for o in olay)
        )

    def test_binance_30_ekim_15_tek_satir(self):
        # Onceden iki Binance olayi (~3.16) iki satirdaydi: capraz ciftler yalniz "binance"
        # paylasiyordu. Secim aninda ozne birlestirmesi tek satira indirir.
        self.assertEqual(self.satir_sayisi(ist('2026-10-30 15:00'), 'Binance'), 1)

    def test_php2shell_22_ekim_21_tek_satir(self):
        # Onceden 10-22 18:15-23:00 arasi PHP2Shell iki satirdaydi; uydurma ad kurali birlestirir.
        self.assertEqual(self.satir_sayisi(ist('2026-10-22 21:00'), 'PHP2Shell'), 1)

    def test_gpt_olayinda_ilgisiz_aws_yazilari_yok(self):
        simdi = ist('2026-10-01 20:00')
        olaylar = olaylari_grupla(penceredeki(list(fikstur()), simdi))
        gpt = olay_of(olaylar, 'ai', 1008)  # AWS: "...GPT-6.1 Sol on Amazon Bedrock"
        # Satici blogunun ayni urun adini (Amazon Bedrock AgentCore) paylasan ilgisiz iki yazisi
        # GPT-6.1 olayina zincirlenmez (ayni kaynak kurali).
        self.assertNotEqual(olay_of(olaylar, 'ai', 992), gpt)
        self.assertNotEqual(olay_of(olaylar, 'ai', 1028), gpt)
        aws = [o.id for o in olaylar[gpt] if o.source == 'AWS ML Blog']
        self.assertEqual(aws, [1008])  # yalniz GPT-6.1 Sol'un Bedrock'a gelisini anlatan yazi


class KuralTest(SimpleTestCase):
    simdi = ist('2026-11-02 12:00')

    def grup_sayisi(self, ogeler):
        return len(olaylari_grupla(ogeler))

    def test_uydurma_ad_ve_cve_tek_basina_baglar(self):
        s = self.simdi
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Zorp2Shell bug hits routers', s),
            oge(2, 'B', 'Vendors scramble over Zorp2Shell', s),
        ]), 1)
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Patch now for CVE-2026-12345', s),
            oge(2, 'B', 'Exploit published for CVE-2026-12345 in routers', s),
        ]), 1)
        # Farkli CVE, genel harf+rakam adi (GPT-6.1) ve ISC2 tek basina baglamaz.
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Patch now for CVE-2026-12345', s),
            oge(2, 'B', 'Exploit published for CVE-2026-54321 in routers', s),
        ]), 2)
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'GPT-6.1 tops coding benchmark', s),
            oge(2, 'B', 'Startup builds chatbot on GPT-6.1', s),
        ]), 2)
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'ISC2 survey finds talent shortage', s),
            oge(2, 'B', 'ISC2 names new board chair', s),
        ]), 2)

    def test_ayni_kaynak_yalniz_yuksek_benzerlikle_baglanir(self):
        s = self.simdi
        a = 'Zorblax ransomware hits hospital chain'
        b = 'Zorblax gang leaks hospital files'
        self.assertEqual(self.grup_sayisi([oge(1, 'A', a, s), oge(2, 'B', b, s)]), 1)
        self.assertEqual(self.grup_sayisi([oge(1, 'A', a, s), oge(2, 'A', b, s)]), 2)
        # Uydurma ad da ayni kaynakta tek basina baglamaz.
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Zorp2Shell bug hits routers', s),
            oge(2, 'A', 'Vendors scramble over Zorp2Shell', s),
        ]), 2)

    def test_secimde_ayni_ozneli_olaylar_birlesir(self):
        s = self.simdi
        ogeler = [
            oge(1, 'A', 'Quixly probes potential crypto theft', s - timedelta(hours=4)),
            oge(2, 'B', 'Quixly confirms crypto theft, freezes withdrawals', s - timedelta(hours=3)),
            oge(3, 'C', 'Quixly hit by record heist', s - timedelta(hours=2)),
            oge(4, 'D', 'Quixly heist blamed on insiders', s - timedelta(hours=1)),
        ]
        self.assertEqual(self.grup_sayisi(ogeler), 2)  # capraz ciftler yalniz "quixly" paylasir
        secim = olaylari_sec(ogeler, s)
        self.assertEqual(len(secim), 1)
        self.assertEqual((secim[0]['kaynak_sayisi'], secim[0]['makale_sayisi']), (4, 4))
        self.assertEqual(secim[0]['puan'], round(olay_puani(ogeler, s), 2))

    def test_secimde_farkli_ozneli_olaylar_birlesmez(self):
        s = self.simdi
        ogeler = [
            oge(1, 'A', 'Drupal Commerce Core flaw exploited', s - timedelta(hours=4)),
            oge(2, 'B', 'Drupal warns of Commerce Core attacks', s - timedelta(hours=3)),
            oge(3, 'C', 'Adobe Commerce shops breached via Brotli', s - timedelta(hours=2)),
            oge(4, 'D', 'Adobe Commerce Brotli bug hits retailers', s - timedelta(hours=1)),
        ]
        self.assertEqual(len(olaylari_sec(ogeler, s)), 2)


class SentetikTest(SimpleTestCase):
    simdi = ist('2026-11-02 12:00')

    def test_ayni_kaynak_tekrari_tek_kaynak(self):
        s = self.simdi
        surumler = [
            oge(1, 'GitHub Releases', 'Argo CD v3.2.1 released', s - timedelta(hours=5), bolum='kubernetes'),
            oge(2, 'GitHub Releases', 'Argo CD v3.2.2 released', s - timedelta(hours=3), bolum='kubernetes'),
            oge(3, ' github releases ', 'Argo CD v3.2.3 released', s - timedelta(hours=1), bolum='kubernetes'),
        ]
        olay = [
            oge(10, 'Bleeping Computer', 'Zorblax ransomware hits hospital chain', s - timedelta(hours=10)),
            oge(11, 'SecurityWeek', 'Zorblax Ransomware Attack Disrupts Hospital Chain', s - timedelta(hours=9)),
        ]
        olaylar = olaylari_grupla(surumler + olay)
        argo = [g for g in olaylar if g[0].source.strip().casefold() == 'github releases']
        self.assertEqual(len(argo), 1)
        self.assertEqual(len(argo[0]), 3)

        secim = olaylari_sec(surumler + olay, s)
        self.assertEqual(len(secim), 2)
        self.assertIn('Zorblax', secim[0]['temsilci'].baslik)
        self.assertEqual(secim[0]['kaynak_sayisi'], 2)
        # Surum notlari cok kaynakli bolume girmez; tek dolgu satiri olur.
        self.assertEqual(secim[1]['kaynak_sayisi'], 1)
        self.assertEqual(secim[1]['makale_sayisi'], 1)
        self.assertEqual(secim[1]['temsilci'].id, 3)

    def test_cok_kaynak_yoksa_en_yeni_ile_dolar(self):
        s = self.simdi
        basliklar = [
            'Quarterly earnings beat expectations', 'Retail chain opens flagship store',
            'Weather service issues storm advisory', 'Museum unveils restored painting',
            'Football club signs young striker', 'City council approves bike lanes',
            'Bakery wins regional bread award', 'Train timetable changes next month',
        ]
        ogeler = [oge(i, f'Kaynak {i}', b, s - timedelta(hours=i * 2 + 1)) for i, b in enumerate(basliklar)]
        secim = olaylari_sec(ogeler, s)
        self.assertEqual(len(secim), 6)
        self.assertEqual([x['temsilci'].id for x in secim], [0, 1, 2, 3, 4, 5])
        zamanlar = [x['son'] for x in secim]
        self.assertEqual(zamanlar, sorted(zamanlar, reverse=True))
        for x in secim:
            self.assertEqual((x['kaynak_sayisi'], x['makale_sayisi']), (1, 1))
            self.assertEqual(x['ilk'], x['son'])

    def test_temsilci_en_iyi_ceviri_sonra_en_erken(self):
        s = self.simdi
        a = oge(1, 'A', 't', s - timedelta(hours=9), ceviri='google')
        b = oge(2, 'B', 't', s - timedelta(hours=5), ceviri='gemini')
        c = oge(3, 'C', 't', s - timedelta(hours=3), ceviri='gemini')
        d = oge(4, 'D', 't', s - timedelta(hours=20), ceviri='gemini', tr_baslik='')
        e = oge(5, 'E', 't', s - timedelta(hours=8), ceviri='libretranslate')
        self.assertEqual(temsilci([a, b, c, d, e]).id, 2)   # gemini, en erken giren
        self.assertEqual(temsilci([a, d, e]).id, 1)         # google > libretranslate > bos baslik
        self.assertEqual(temsilci([d, e]).id, 5)            # bos turkish_title en sona duser
        f = oge(6, 'F', 't', s - timedelta(hours=4), ceviri='openrouter')
        g = oge(7, 'G', 't', s - timedelta(hours=6), ceviri='deepl')
        self.assertEqual(temsilci([f, g, a]).id, 7)         # openrouter = deepl; esitlikte en erken
        h = oge(8, 'H', 't', s - timedelta(hours=6), ceviri='deepl')
        self.assertEqual(temsilci([h, g]).id, 7)            # ayni an: en kucuk id

    def test_puan_formulu(self):
        s = self.simdi

        def olay(baslik_ek=''):
            return [
                oge(1, 'A', 'Olay bir' + baslik_ek, s),
                oge(2, 'B', 'Olay iki', s),
                oge(3, 'C', 'Olay uc', s),
                oge(4, 'A', 'Olay dort', s),
            ]
        self.assertAlmostEqual(olay_puani(olay(), s), 3.5)
        self.assertAlmostEqual(olay_puani(olay(), s + timedelta(hours=24)), 1.75)
        self.assertAlmostEqual(olay_puani(olay(' hacked'), s), 5.0)
        self.assertAlmostEqual(olay_puani(olay(' hacked'), s + timedelta(hours=24)), 2.5)

    def test_taze_kapsam_esit_buyuklukte_eskiyi_gecer(self):
        """Ayni boyutta (3 kaynak, 3 makale) ve en yeni makalesi ayni anda olan iki olaydan
        kapsami taze olan one gecer (10-30: taze Binance > uc gune yayilmis PHP2Shell)."""
        s = self.simdi
        son = s - timedelta(hours=2)
        taze = [oge(1, 'A', 'x', son - timedelta(hours=1)), oge(2, 'B', 'x', son - timedelta(hours=1)),
                oge(3, 'C', 'x', son)]
        eski = [oge(4, 'A', 'y', son - timedelta(hours=48)), oge(5, 'B', 'y', son - timedelta(hours=40)),
                oge(6, 'C', 'y', son)]
        self.assertGreater(olay_puani(taze, s), olay_puani(eski, s))
        # Tek kaynakli eski makale yerine ayni kaynagin taze tekrari da puani artirir.
        self.assertGreater(olay_puani(eski + [oge(7, 'A', 'y', son)], s), olay_puani(eski, s))

    def test_pencere_72_saat_ve_4_gun(self):
        s = ist('2026-11-02 01:00')  # UTC 11-01 22:00; yerel tarih 11-02
        ogeler = [
            oge(1, 'A', 'icerde', s - timedelta(hours=71, minutes=59)),
            oge(2, 'A', 'sinirda', s - timedelta(hours=72)),
            oge(3, 'A', '72 saati asmis', s - timedelta(hours=72, minutes=1)),
            oge(4, 'A', 'gelecekte', s + timedelta(minutes=1)),
            oge(5, 'A', 'yayin 4 gun once', s - timedelta(hours=1), yayin=date(2026, 10, 29)),
            oge(6, 'A', 'yayin 5 gun once', s - timedelta(hours=1), yayin=date(2026, 10, 28)),
            oge(7, 'A', 'yayin bos', s - timedelta(hours=1), yayin=None),
        ]
        # 6: UTC tarihi (11-01) ile 4 gun once 10-28 olurdu; kural yerel tarihe (11-02) gore.
        self.assertEqual(sorted(o.id for o in penceredeki(ogeler, s)), [1, 2, 5, 7])
        self.assertEqual(penceredeki(ogeler, s.astimezone(timezone.utc)), penceredeki(ogeler, s))

    def test_sira_bagimsiz_ve_deterministik(self):
        simdi = ist('2026-10-30 20:00')
        ogeler = list(fikstur())
        ilk = olaylari_sec(ogeler, simdi)
        self.assertEqual(olaylari_sec(ogeler, simdi), ilk)
        karisik = ogeler[:]
        random.Random(20261105).shuffle(karisik)
        self.assertEqual(olaylari_sec(karisik, simdi), ilk)
        self.assertEqual(olaylari_sec(list(reversed(ogeler)), simdi), ilk)

        pencere = penceredeki(ogeler, simdi)
        gruplar = olaylari_grupla(pencere)
        self.assertEqual(olaylari_grupla(list(reversed(pencere))), gruplar)
