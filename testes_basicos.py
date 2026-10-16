"""Testes rápidos de homologação para DG Cortes. Rodar: py testes_basicos.py
Usa um banco TEMPORÁRIO, sem tocar os cadastros reais.
"""
import os, sys, tempfile, unittest
from datetime import timedelta
from pathlib import Path

TEST_DIR=tempfile.TemporaryDirectory(prefix='dgcortes_teste_')
os.environ['DG_DB_PATH']=str(Path(TEST_DIR.name)/'teste.sqlite3')
os.environ['DG_DATA_DIR']=TEST_DIR.name
os.environ['RENDER']=''
os.environ['SETUP_TOKEN']=''
sys.path.insert(0,str(Path(__file__).resolve().parent))
import app as dg

dg.notify_appointment=lambda *args,**kwargs: None # Nunca dispara notificações durante testes

class TesteAgendamento(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner=dg.app.test_client()
        cls.csrf=cls.owner.get('/api/bootstrap').get_json()['csrf']
        r=cls.owner.post('/api/setup', json={'name':'Dono Teste','phone':'71999999999','email':'dono@teste.invalid','password':'SenhaTeste123'},headers={'X-CSRF-Token':cls.csrf})
        assert r.status_code==200, r.get_json()
        cls.csrf=cls.owner.get('/api/bootstrap').get_json()['csrf']
        cls.guest=dg.app.test_client()
        cls.gcsrf=cls.guest.get('/api/bootstrap').get_json()['csrf']
        cls.day=dg.now().date()+timedelta(days=1)
        while cls.day.weekday()==6:
            cls.day+=timedelta(days=1)
        cls.day=cls.day.isoformat()
        state=cls.guest.get('/api/state').get_json()
        cls.barber=state['barbers'][0]['id']
        cls.service=next(x['id'] for x in state['services'] if x['duration']==30)

    def test_01_proprietario_foi_criado(self):
        r=self.owner.get('/api/bootstrap').get_json()
        self.assertTrue(r['installed'])
        self.assertEqual(r['user']['role'],'owner')

    def test_02_sem_csrf_nao_altera_dados(self):
        r=self.guest.post('/api/book', json={})
        self.assertEqual(r.status_code,403)

    def test_03_agendamento_conflito(self):
        slots=self.guest.get('/api/availability',query_string={'barber_id':self.barber,'service_id':self.service,'day':self.day}).get_json()['slots']
        self.assertTrue(slots, 'Nenhum horário disponível para teste')
        payload={'barber_id':self.barber,'service_id':self.service,'day':self.day,'time':slots[0],
                 'name':'Cliente Teste','phone':'71988887777','email':'cliente@teste.invalid'}
        first=self.guest.post('/api/book',json=payload,headers={'X-CSRF-Token':self.gcsrf})
        self.assertEqual(first.status_code,200,first.get_json())
        second=self.guest.post('/api/book',json=payload,headers={'X-CSRF-Token':self.gcsrf})
        self.assertEqual(second.status_code,400,'O mesmo horário não pode ser reservado duas vezes')
        proof=self.guest.get(f"/api/appointments/{first.get_json()['id']}/confirmation",query_string={'token':first.get_json()['token']})
        self.assertEqual(proof.status_code,200)
        self.assertEqual(proof.get_json()['day'],self.day)

    def test_04_visitante_nao_acessa_administracao(self):
        r=self.guest.post('/api/staff',json={'name':'Invasor Teste'},headers={'X-CSRF-Token':self.gcsrf})
        self.assertEqual(r.status_code,401)

    def test_05_limite_cinco_barbeiros(self):
        for i in range(5):
            data={'name':f'Barbeiro Teste{i}', 'email':f'barbeiro{i}@teste.invalid', 'phone':'71988887777', 'password':'SenhaForteTeste123'}
            r=self.owner.post('/api/staff',json=data,headers={'X-CSRF-Token':self.csrf})
            self.assertEqual(r.status_code,200,r.get_json())
        data={'name':'Sexto Barbeiro', 'email':'sexto@teste.invalid', 'phone':'71988887777', 'password':'SenhaForteTeste123'}
        r=self.owner.post('/api/staff',json=data,headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(r.status_code,400)

    def test_06_dono_nao_pode_ser_desativado(self):
        state=self.owner.get('/api/state').get_json()
        oid=next(u['id'] for u in state['users'] if u['role']=='owner')
        r=self.owner.post(f'/api/users/{oid}/active',json={'active':False},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(r.status_code,400)

if __name__=='__main__':
    try:
        unittest.main(verbosity=2,exit=False)
    finally:
        TEST_DIR.cleanup()
