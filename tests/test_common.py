from unittest import TestCase
from sqlalchemy.orm import relationship, joinedload
from mortar_mixins.common import Common
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from testfixtures import compare
from mortar_rdb import get_session
from mortar_rdb.testing import register_session


class MoreTests(TestCase):

    def setUp(self):
        self.Base = declarative_base()
        class Model(Common, self.Base):
            id = Column(Integer, primary_key=True)
        self.Model = Model

    def test_table_name(self):
        compare(self.Model.__table__.name, 'model')

    def test_eq_wrong_type(self):
        self.assertFalse(self.Model() == object())

    def test_eq_wrong_model_type(self):
        class OtherModel(Common, self.Base):
            id = Column(Integer, primary_key=True)
        self.assertFalse(self.Model(id=1) == OtherModel(id=1))

    def test_eq_different(self):
        self.assertFalse(self.Model(id=1) == self.Model(id=2))

    def test_eq_different_keys(self):
        self.assertFalse(self.Model() == self.Model(id=2))

    def test_eq_same(self):
        self.assertTrue(self.Model(id=1) == self.Model(id=1))

    def test_ne_wrong_type(self):
        self.assertTrue(self.Model() != object())

    def test_ne_wrong_model_type(self):
        class OtherModel(Common, self.Base):
            id = Column(Integer, primary_key=True)
        self.assertTrue(self.Model(id=1) != OtherModel(id=1))

    def test_ne_different(self):
        self.assertTrue(self.Model(id=1) != self.Model(id=2))

    def test_ne_same(self):
        self.assertTrue(self.Model(id=1) != self.Model(id=2))

    def test_repr(self):
        compare('Model(id=1)', repr(self.Model(id=1)))

    def test_str(self):
        compare('Model(id=1)', str(self.Model(id=1)))


class CompareTests(TestCase):

    def setUp(self):
        register_session(transactional=False)

        Base = declarative_base()

        class Model(Common, Base):
            id =  Column(Integer, primary_key=True)

        class AnotherModel(Common, Base):
            id = Column(Integer, primary_key=True)
            attr = Column(Integer)
            other_id = Column(Integer, ForeignKey('model.id'))
            other = relationship("Model")

        self.Model = Model
        self.AnotherModel = AnotherModel

        self.session = get_session()
        self.addCleanup(self.session.rollback)
        Base.metadata.create_all(self.session.bind)

    def check_raises(self, x, y, message, **kw):
        try:
            compare(x, y , **kw)
        except Exception as e:
            if not isinstance(e, AssertionError):
                raise # pragma: no cover
            actual = e.args[0]
            if actual != message: # pragma: no cover
                self.fail(compare(actual, expected=message,
                                  show_whitespace=True,
                                  raises=False))
        else: # pragma: no cover
            self.fail('No exception raised!')

    def test_identical(self):
        compare(
            [self.Model(id=1), self.Model(id=2)],
            [self.Model(id=1), self.Model(id=2)]
            )

    def test_different(self):
        self.check_raises(
            self.Model(id=1), self.Model(id=2),
            "Model not as expected:\n"
            "\n"
            "values differ:\n"
            "'id': 1 != 2"
        )

    def test_different_types(self):
        self.check_raises(
            self.Model(id=1), self.AnotherModel(id=1),
            "Model(id=1) != AnotherModel(id=1)"
        )

    def test_db_versus_non_db_equal(self):
        self.session.add(self.Model(id=1))
        self.session.add(self.AnotherModel(id=2, other_id=1))
        self.session.commit()

        db = self.session\
            .query(self.AnotherModel)\
            .options(joinedload(self.AnotherModel.other, innerjoin=True))\
            .one()

        raw = self.AnotherModel(id=2, other_id=1)

        compare(db, raw)

    def test_db_versus_non_db_not_equal(self):
        self.session.add(self.Model(id=1))
        self.session.add(self.AnotherModel(id=2, other_id=1))
        self.session.commit()

        db = self.session\
            .query(self.AnotherModel)\
            .options(joinedload(self.AnotherModel.other, innerjoin=True))\
            .one()

        raw = self.AnotherModel(id=2, other=self.Model(id=2), attr=6)

        self.check_raises(
            db, raw,
            "AnotherModel not as expected:\n"
            "\n"
            "same:\n"
            "['id']\n"
            "\n"
            "values differ:\n"
            "'attr': None != 6\n"
            "'other_id': 1 != None"
        )

    def test_db_versus_non_db_not_equal_check_relationship(self):
        self.session.add(self.Model(id=1))
        self.session.add(self.AnotherModel(id=2, other_id=1))
        self.session.commit()

        db = self.session\
            .query(self.AnotherModel)\
            .options(joinedload(self.AnotherModel.other, innerjoin=True))\
            .one()

        raw = self.AnotherModel(id=2, other=self.Model(id=2), attr=6)

        self.check_raises(
            db, raw,
            "AnotherModel not as expected:\n"
            "\n"
            "same:\n"
            "['id']\n"
            "\n"
            "values differ:\n"
            "'attr': None != 6\n"
            "'other': Model(id=1) != Model(id=2)\n"
            "'other_id': 1 != None\n"
            '\n'
            "While comparing ['other']: Model not as expected:\n"
            '\n'
            'values differ:\n'
            "'id': 1 != 2",
            check_relationships=True,
        )
