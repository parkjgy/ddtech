# 이지체크 Server

서버 반영시 ( 개발 )
### Ubuntu 상의 Service 등록 파일 ( 참고용 )
```
# /etc/systemd/system/aegis-dev.service
[Unit]
Description=Aegis Server Dev

[Service]
Type=simple
User=ddtechi
ExecStart=/home/ddtechi/ddtech/ddtenv/bin/python /home/ddtechi/ddtech/aegis/manage.py runserver 0.0.0.0:8000 --settings=config.settings.development

[Install]
WantedBy=multi-user.target
```

### 등록된 Service의 Control ( 참고용 )
```
sudo service aegis-dev start # Start
sudo service aegis-dev stop # Stop
sudo service aegis-dev restart # Restart
```

### GitHub Master Branch의 변경 사항을 반영 
```
cd ~/ddtech/aegis
git reset --hard HEAD # local changed 가 존재할 경우
git pull
# GitHub 아이디 및 비밀번호 입력

# 아래부터는 Migrate시
source ../ddtenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings.development
./manage.py makemigrations
./manage.py makemigrations customer # customer/models.py 의 변경점은 있으나, Django System 에서 인식하지 않을 경우
./manage.py makemigrations employee # employee/models.py 의 변경점은 있으나, Django System 에서 인식하지 않을 경우
./manage.py makemigrations operation # operation/models.py 의 변경점은 있으나, Django System 에서 인식하지 않을 경우
./manage.py migrate
```
