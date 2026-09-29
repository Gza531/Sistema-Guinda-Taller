from django.db import models

# Create your models here.

from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    id_usuario = models.AutoField(primary_key=True)

    class Meta:
        db_table = "usuarios"

    def __str__(self):
        return self.username