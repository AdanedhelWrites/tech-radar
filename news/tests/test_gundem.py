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
        gpt = olay_of(olaylar, 'ai', 997)  # TechCrunch: "OpenAI launches GPT-6.1 Sol, ..."
        # Satici blogunun ayni urun adini (Amazon Bedrock AgentCore) paylasan ilgisiz iki yazisi
        # GPT-6.1 olayina zincirlenmez (ayni kaynak kurali).
        self.assertNotEqual(olay_of(olaylar, 'ai', 992), gpt)
        self.assertNotEqual(olay_of(olaylar, 'ai', 1028), gpt)
        # Yalniz GPT-6.1 Sol'un Bedrock'a gelisini anlatan yazi (1008) olayda: ayni surumlu
        # urun adi obegini ("GPT-6.1 Sol") tasir.
        self.assertEqual([o.id for o in olaylar[gpt] if o.source == 'AWS ML Blog'], [1008])

    def test_surumlu_urun_obegi_cikislari_toplar(self):
        olaylar = olaylari_grupla(penceredeki(list(fikstur()), ist('2026-10-01 20:00')))
        sol = olay_of(olaylar, 'ai', 997)
        self.assertEqual(
            sorted((o.source for o in olaylar[sol])),
            ['AWS ML Blog', 'MarkTechPost', 'OpenAI Blog', 'TechCrunch AI'],
        )
        self.assertNotEqual(olay_of(olaylar, 'news', 714), sol)  # "OpenAI Shelves GPT-6.1 Astra"
        olaylar = olaylari_grupla(penceredeki(list(fikstur()), ist('2026-10-28 12:00')))
        terra = {olay_of(olaylar, b, i) for b, i in [('ai', 1651), ('ai', 1655), ('news', 1817), ('news', 1891)]}
        self.assertEqual(len(terra), 1)  # "Introducing GPT-6.1 Terra" dahil dort kaynak tek olay

    def test_gpt6_astra_obegi_basis_yazisini_zincirlemez(self):
        # OpenAI Blog "Basis completes a tax workbook 2x faster with GPT-6 Astra" (974) yalniz
        # "GPT-6 Astra" obegini (iki sozcuk, tek ad) paylasiyordu; GPT-6.1 Sol olayina girmez.
        simdi = ist('2026-10-01 20:00')
        olaylar = olaylari_grupla(penceredeki(list(fikstur()), simdi))
        self.assertNotEqual(olay_of(olaylar, 'ai', 974), olay_of(olaylar, 'ai', 997))
        self.assertEqual(len(olaylar[olay_of(olaylar, 'ai', 974)]), 1)

    def test_west_virginia_tek_ad_obegi_birlestirmez(self):
        # The Record 1938 "Court strikes down West Virginia law..." ile TechCrunch 1800
        # "Nvidia weighs ... AI data center in West Virginia".
        simdi = ist('2026-10-31 12:00')
        olaylar = olaylari_grupla(penceredeki(list(fikstur()), simdi))
        self.assertNotEqual(olay_of(olaylar, 'news', 1938), olay_of(olaylar, 'ai', 1800))

    def test_genel_sifat_ek_sozcuk_sayilmaz(self):
        # MarkTechPost 1709 "...FlashMap, a Flow Map Drafter for 6.14x Faster LLM Decoding" ile
        # Google Cloud SRE 351 "How to troubleshoot GKE workloads faster with VPC Flow Logs".
        simdi = ist('2026-10-29 12:00')
        olaylar = olaylari_grupla(penceredeki(list(fikstur()), simdi))
        self.assertNotEqual(olay_of(olaylar, 'ai', 1709), olay_of(olaylar, 'sre', 351))


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

    def test_dolgu_satirlari_ozneyle_birlesmez(self):
        # Fiksturdeki ilgisiz cift (The Record 1440, Ars Technica AI 1541): ikisi de "Judge" ile
        # baslar; dolgu satirlari birlesip sahte iki kaynakli olay olmamali.
        s = self.simdi
        ogeler = [
            oge(1440, 'The Record', "Judge denies WhatsApp’s bid to hold spyware maker in contempt for "
                'allegedly targeting users', s - timedelta(hours=2)),
            oge(1541, 'Ars Technica AI', "Judge rejects Trump’s wild claim EPA can dismiss data center "
                'pollution lawsuits', s - timedelta(hours=1), bolum='ai'),
        ]
        secim = olaylari_sec(ogeler, s)
        self.assertEqual(len(secim), 2)
        self.assertEqual([x['kaynak_sayisi'] for x in secim], [1, 1])

    def test_ayni_kaynagin_dolgu_satirlari_birlesmez(self):
        # Google Cloud SRE'nin iki ilgisiz "Accelerating..." yazisi (fikstur 206, 216).
        s = self.simdi
        ogeler = [
            oge(206, 'Google Cloud SRE', 'Accelerating agentic RL and evaluation research velocity with 45x '
                'faster GKE Agent Sandbox', s - timedelta(hours=2), bolum='sre'),
            oge(216, 'Google Cloud SRE', 'Accelerating analytics: PayPal’s journey with Managed Service '
                'for Apache Spark', s - timedelta(hours=1), bolum='sre'),
        ]
        secim = olaylari_sec(ogeler, s)
        self.assertEqual(len(secim), 2)
        self.assertEqual([x['makale_sayisi'] for x in secim], [1, 1])

    def test_siemens_clickfix_ile_chrome_clickfix_birlesmez(self):
        # Siemens basliklari (fikstur 1434, 1479) yalniz Title Case yazilir; "Siemens" ozel ad
        # sayilmasa da ozne olarak yakalanir. Aksi halde iki olayin oznesi "clickfix" olurdu.
        s = self.simdi
        ogeler = [
            oge(1434, 'SecurityWeek', 'Siemens Software Center Vulnerability Exploited in ClickFix Malware Attacks',
                s - timedelta(hours=5)),
            oge(1479, 'Infosecurity Magazine', 'Siemens Customers Targeted by ClickFix Attackers Exploiting '
                'DLL Side-Loading Flaw', s - timedelta(hours=4)),
            oge(1, 'Bleeping Computer', 'ClickFix lures surge as Chrome adds warnings', s - timedelta(hours=3)),
            oge(2, 'The Hacker News', 'ClickFix lures hit Chrome users', s - timedelta(hours=2)),
        ]
        self.assertEqual(self.grup_sayisi(ogeler), 2)
        secim = olaylari_sec(ogeler, s, adet=50)  # tum olaylar satir
        self.assertEqual(len(secim), 2)
        self.assertEqual([x['kaynak_sayisi'] for x in secim], [2, 2])


class SonDuzeltmeTest(SimpleTestCase):
    simdi = ist('2026-11-02 12:00')

    def grup_sayisi(self, ogeler):
        return len(olaylari_grupla(ogeler))

    def test_palo_alto_obegi_tek_ad_sayilir(self):
        s = self.simdi
        ogeler = [
            oge(1, 'Help Net Security', 'Ransomware gangs exploit Palo Alto GlobalProtect VPN flaw', s),
            oge(2, 'The Hacker News', 'Attackers Exploit PHP2Shell Flaws in Internet-Exposed Palo Alto Networks '
                'Management Interfaces', s),
            oge(3, 'SecurityWeek', 'Palo Alto Networks Reports Record Quarterly Revenue', s),
        ]
        self.assertEqual(self.grup_sayisi(ogeler), 3)
        # Karsit kontrol: obek + genel olmayan ek sozcuk ("ransomware") yine baglar.
        self.assertEqual(self.grup_sayisi([
            ogeler[0],
            oge(4, 'The Hacker News', 'Qilin Ransomware Group Exploits Palo Alto Networks Flaw', s),
        ]), 1)

    def test_surumlu_urun_obegi_tek_basina_baglar(self):
        s = self.simdi
        sol = 'OpenAI launches GPT-6.1 Sol, says it nearly matches GPT-6 Astra'
        self.assertEqual(self.grup_sayisi([oge(1, 'A', sol, s), oge(2, 'B', 'Introducing GPT-6.1 Sol', s)]), 1)
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Kubernetes 1.35 released', s),
            oge(2, 'B', 'Kubernetes 1.35 brings sidecar GA', s),
        ]), 1)

    def test_sayili_ama_urun_olmayan_obekler_tek_basina_baglamaz(self):
        s = self.simdi
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Fortinet FortiWeb flaw scores CVSS 9.8', s),
            oge(2, 'B', 'Ivanti EPMM bug rated CVSS 9.8', s),
        ]), 2)
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Inside the breach, Part 1', s),
            oge(2, 'B', 'Building a SOC, Part 1', s),
        ]), 2)
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Retailer files for Chapter 11', s),
            oge(2, 'B', 'Telecom heads to Chapter 11', s),
        ]), 2)
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Hospital chain reports ransomware outage in SEC 8-K', s),
            oge(2, 'B', 'Chipmaker confirms supplier intrusion in SEC 8-K', s),
        ]), 2)
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Python 3.14 released', s),
            oge(2, 'B', 'Python 3.14 brings free threading', s),
        ]), 1)

    def test_doe_durak_sozcuk_degildir(self):
        self.assertNotIn('doe', gundem.DURAK)
        self.assertIn('does', gundem.DURAK)
        self.assertIsNone(gundem._surum_obegi('Fortune 500 firm hit'))

    def test_farkli_ya_da_rakamsiz_obek_tek_basina_baglamaz(self):
        s = self.simdi
        sol = 'OpenAI launches GPT-6.1 Sol, says it nearly matches GPT-6 Astra'
        # Ikinci obek (GPT-6 Astra) basligin surum obegi degildir.
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', sol, s),
            oge(2, 'B', 'Basis completes a tax workbook 2x faster with GPT-6 Astra', s),
        ]), 2)
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Startup builds tooling around GPT-6 Astra', s),
            oge(2, 'B', 'Introducing GPT-6.1 Sol', s),
        ]), 2)
        # Rakamsiz obek ve genel ad + tamsayi obegi tek basina baglamaz.
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Quest Diagnostics reports breach', s),
            oge(2, 'B', 'Quest Diagnostics warns patients', s),
        ]), 2)
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Windows 11 update breaks printers', s),
            oge(2, 'B', 'Windows 11 adds redesigned Start menu', s),
        ]), 2)

    def test_yil_sozcugu_atilir(self):
        s = self.simdi
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Salesforce plans agent marketplace for 2027', s),
            oge(2, 'B', 'Salesforce raises outlook through 2027', s),
        ]), 2)
        self.assertEqual(self.grup_sayisi([
            oge(1, 'A', 'Zorblax plans expansion by 2031', s),
            oge(2, 'B', 'Zorblax board meets in 1999 archive', s),
        ]), 2)
        self.assertNotIn('2027', gundem.DURAK)

    def test_ozne_birlesmesi_zaman_sinirli(self):
        s = self.simdi
        eski = [
            oge(1, 'A', 'Ivanti patches gateway flaw', s - timedelta(days=4, hours=2)),
            oge(2, 'B', 'Ivanti gateway flaw exploited', s - timedelta(days=4, hours=1)),
        ]
        yeni = [
            oge(3, 'C', 'Ivanti discloses breach of support portal', s - timedelta(hours=2)),
            oge(4, 'D', 'Ivanti support portal breach confirmed', s - timedelta(hours=1)),
        ]
        hepsi = eski + yeni
        sirali = sorted(hepsi, key=lambda o: (o.bolum, o.id))
        ozellik_listesi = gundem._baslik_ozellikleri(sirali)
        ozellik = {(o.bolum, o.id): oz for o, oz in zip(sirali, ozellik_listesi)}
        olaylar = gundem._grupla(sirali, ozellik_listesi)
        self.assertEqual(len(olaylar), 2)
        satirlar, birlesmeler = gundem._secip_birlestir(olaylar, s, 6, ozellik)
        self.assertEqual(birlesmeler, [])  # 4 gun arayla iki ayri Ivanti olayi
        self.assertEqual(len(satirlar), 2)
        # Ayni iki olay 24 saat icindeyse birlesir.
        yakin = [oge(o.id, o.source, o.baslik, o.created_at + timedelta(days=4) - timedelta(hours=10))
                 for o in eski] + yeni
        self.assertEqual(len(olaylari_sec(yakin, s)), 1)

    def test_bozuk_girdide_hata_vermez(self):
        s = self.simdi
        self.assertEqual(olaylari_sec([], s), [])
        ogeler = [
            oge(1, None, None, s - timedelta(hours=1), ceviri=None, tr_baslik=None),
            oge(2, '', '', s - timedelta(hours=2), ceviri='', tr_baslik=''),
            oge(3, 'A', 'the and of to in', s - timedelta(hours=3)),
            oge(4, 'B', '北京的网络安全事件', s - timedelta(hours=4)),
            oge(5, 'C', 'İstanbul’da güvenlik açığı çözüldü',
                s - timedelta(hours=5)),
            oge(6, 'D', 'Zorblax ' * 2500, s - timedelta(hours=6)),
            oge(7, 'E', 'Zorblax ' * 2500, s - timedelta(hours=7)),
        ]
        secim = olaylari_sec(ogeler, s)
        self.assertEqual(len(secim), 6)
        self.assertTrue(all(isinstance(x['puan'], float) for x in secim))


class OzetBaslikTest(SimpleTestCase):
    """Cok konulu ozet basliklari (bulten, haftalik ozet, ';' ile baglanan iki haber) en fazla
    bir olaya katilir ve yalniz tekrar sayilir: iki olay arasinda kopru kurmaz, bir olayi
    cok kaynakli yapmaz."""
    simdi = ist('2026-11-02 12:00')

    def test_fiksturdeki_ozet_basliklari_taninir(self):
        basliklar = {(o.bolum, o.id): o.baslik for o in fikstur()}
        ozet = [
            ('news', 700), ('news', 754), ('news', 1383), ('news', 1384), ('news', 1388), ('news', 1402),
            ('news', 1628), ('news', 1655), ('news', 1663), ('news', 1992), ('news', 2007), ('news', 2038),
            ('news', 2094), ('news', 2149), ('news', 2155), ('ai', 1831),
        ]
        for anahtar in ozet:
            self.assertTrue(gundem._ozet_mi(basliklar[anahtar]), basliklar[anahtar])
        tek_haber = [
            ('news', 1844),  # "iOS, macOS 27.2 Patch 286 Bugs; Fix for Exploited Flaw Backported to iOS 18"
            ('ai', 1861),    # "Apple Watch's AI features for rewinding and recapping conversations..."
            ('ai', 979),     # "Roundtables: The Deadly Failures of The Virtual Border Wall"
            ('ai', 1010),    # "OpenAI repotedly in talks to raise $30B round at $1.4T valuation"
            ('news', 710),   # "AI Agents Are Privileged Users; Who Is Auditing Their Access?"
            ('news', 1607), ('news', 1953), ('news', 1978),
        ]
        for anahtar in tek_haber:
            self.assertFalse(gundem._ozet_mi(basliklar[anahtar]), basliklar[anahtar])

    def test_ozet_iki_olayi_kopruyle_birlestirmez(self):
        # Help Net Security 1992 hem VMware ESX hem PHP2Shell olayini anar. Gercek PHP2Shell ve
        # VMware basliklari (fikstur 1978, 1915, 1953) ile ona "chained" uzerinden baglanan bir
        # VMware basligi: ozet kopru olsaydi dort haber tek olay olurdu.
        s = self.simdi
        php = [
            oge(1978, 'Bleeping Computer', 'CISA warns of Fragnesia Linux flaw chained in PHP2Shell attacks', s),
            oge(1915, 'SecurityWeek', 'China-Linked Hackers Exploit PHP2Shell to Root Firewalls', s),
        ]
        vmware = [
            oge(1953, 'The Hacker News', 'China-Linked Hackers Exploited VMware ESX Zero-Day to Reduce Audit '
                'Trail Visibility', s),
            oge(1, 'The Register', 'Chinese spies chained VMware ESX zero-day to dodge audit logs', s),
        ]
        ozet = oge(1992, 'Help Net Security', 'Chinese hackers used VMware ESX zero-day; PHP2Shell and '
                   'Fragnesia chained to root firewalls', s)
        olaylar = olaylari_grupla(php + vmware + [ozet])
        self.assertNotEqual(olay_of(olaylar, 'news', 1978), olay_of(olaylar, 'news', 1953))
        self.assertEqual(olay_of(olaylar, 'news', 1978), olay_of(olaylar, 'news', 1915))
        self.assertEqual(olay_of(olaylar, 'news', 1953), olay_of(olaylar, 'news', 1))
        # Iki olaya birden uyan ozet hicbirine katilmaz (supheli durumda ayri tut).
        self.assertEqual(len(olaylar[olay_of(olaylar, 'news', 1992)]), 1)
        # Yalniz bir olaya uyuyorsa o olaya tekrar olarak katilir, kaynak sayisini artirmaz.
        secim = olaylari_sec(php + [ozet], s)
        self.assertEqual(len(secim), 1)
        self.assertEqual((secim[0]['kaynak_sayisi'], secim[0]['makale_sayisi']), (2, 3))
        self.assertNotIn('Help Net Security', secim[0]['kaynaklar'])
        self.assertNotEqual(secim[0]['temsilci'].id, 1992)

    def test_fikstur_29_ekim_vmware_php2shell_ayri(self):
        simdi = ist('2026-10-30 00:00')
        olaylar = secilen_olaylar(fikstur(), simdi, adet=1000)
        php = olay_of(olaylar, 'news', 1978)
        self.assertNotEqual(php, olay_of(olaylar, 'news', 1953))
        self.assertNotEqual(php, olay_of(olaylar, 'news', 1966))
        secim = olaylari_sec(list(fikstur()), simdi)
        self.assertIn('PHP2Shell', secim[0]['temsilci'].baslik)
        self.assertNotIn('Help Net Security', secim[0]['kaynaklar'])

    def test_bulten_tek_signal_haberini_cok_kaynakli_yapmaz(self):
        # 10-25 15:00-18:00: SecurityWeek 1607 "Signal Vulnerability Lets Malicious Callers Block
        # Hang-Ups" ile THN 1628 "ThreatsDay: ... Signal Hang-Up Flaw, ... + 21 More" iki kaynakli
        # olay sayiliyordu.
        for saat in ('2026-10-25 15:00', '2026-10-25 18:00'):
            secim = olaylari_sec(list(fikstur()), ist(saat), adet=1000)
            signal = [x for x in secim if 'Signal' in x['temsilci'].baslik]
            self.assertTrue(signal)
            for x in signal:
                self.assertEqual(x['kaynak_sayisi'], 1, saat)
            self.assertFalse(any(x['kaynak_sayisi'] >= 2 and x['temsilci'].id == 1628 for x in secim))

    def test_ozetler_birbirine_baglanmaz(self):
        s = self.simdi
        ogeler = [
            oge(1, 'The Hacker News', 'ThreatsDay: Zorblax Ransomware, Quixly Heist, Router Botnet + 12 More', s),
            oge(2, 'Help Net Security', 'Week in review: Zorblax ransomware, Quixly heist, router botnet', s),
        ]
        self.assertEqual(len(olaylari_grupla(ogeler)), 2)
        self.assertEqual([x['kaynak_sayisi'] for x in olaylari_sec(ogeler, s)], [1, 1])
        # Ayni kaynagin ardisik bultenleri (fikstur 1388, 1390) ayni kaynak kuraliyla tek olay
        # kalir; yoksa iki dolgu satiri kaplardi.
        bultenler = [
            oge(1388, 'Security Affairs', 'SECURITY AFFAIRS AI-CYBERSECURITY NEWSLETTER ROUND 4', s),
            oge(1390, 'Security Affairs', 'SECURITY AFFAIRS MALWARE NEWSLETTER ROUND 119', s),
        ]
        self.assertEqual(len(olaylari_grupla(bultenler)), 1)
        self.assertEqual(len(olaylari_sec(bultenler, s)), 1)


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
