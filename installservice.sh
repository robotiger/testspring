sudo cp testspring.service /etc/systemd/system
sudo cp testspring_web.service  /etc/systemd/system
sudo systemctl enable testspring.service
sudo systemctl enable testspring_web.service
sudo systemctl start testspring.service
sudo systemctl start testspring_web.service
