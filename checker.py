#!/usr/bin/env python

import os
import ast
import sys
import configparser
import collections
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile

# The idea is that we will loop through each reservation page
# based on the data below.  When we reach one which is available,
# we will enter reservation info and take the user to checkout -
# at this point the reservation is held for 15 minutes and the user
# can enter payment details.

URL = ('http://www.recreation.gov/campsiteDetails.do?'
       'siteId={site_id}&contractCode=NRSO&parkId={park_id}&'
       'arvdate={arrival}&lengthOfStay={length}')

RED = 'rgb(255, 72, 0)'

logger = logging.getLogger()

RETRIES = 2
USERNAME = None
PASSWORD = None
NUM_RESERVATIONS = 2


def find_available_sites(driver, sites, arrival, length):
  available_sites = []
  for site in sites:
    if trip_available(driver, site, arrival, length):
      available_sites.append(site)
  return available_sites


def trip_available(driver, site, arrival, length):
  """Check if |site| is available for the length."""
  trip = site.copy()
  trip['arrival'] = arrival
  trip['length'] = length
  url = URL.format(**trip)

  for i in range(RETRIES):
    driver.get(url) 
    avail = WebDriverWait(driver, 3).until(
        EC.presence_of_element_located((By.ID, 'avail1')))
    if avail.text == 'N':
        driver.refresh()
        continue
    else:
      # check the border of the arrival date field - a red border indicates
      # the selection is not available. if we find a site, return the value
      try:
        border_color = driver.find_element_by_id(
            'arrivaldate').value_of_css_property('border-top-color')
        if border_color != RED:
          return True
      except Exception as e:
        logger.error(e)

  logger.error('Failed to find availability for site: %s, arrival: %s, '
               'length: %s.' % (str(site), arrival, length))
  return False


def parse_config(config):
  RETRIES = int(config.get('common', 'retries'))
  USERNAME = config.get('common', 'username')
  PASSWORD = config.get('common', 'password')
  NUM_RESERVATIONS = int(config.get('common', 'num_reservations'))


def get_web_driver():
  firefox_profile = FirefoxProfile()
  firefox_profile.set_preference('browser.migration.version', 9001)
  firefox_profile.set_preference('permissions.default.image', 2)
  firefox_profile.set_preference('dom.ipc.plugins.enabled.libflashplayer.so',
      'false')
  driver = webdriver.Firefox(firefox_profile)
  return driver


def main(argv):
  config = configparser.ConfigParser()
  config.read('checker.ini')
  parse_config(config)
  driver = get_web_driver()

  for count in range(1, NUM_RESERVATIONS + 1):
    r = str(count)
    arrival = config.get("reservation_" + r, "arv_date")
    length = config.get("reservation_" + r, "length_of_stay")
    num_occupants = config.get("reservation_" + r, "num_occupants")
    num_vehicles = config.get("reservation_" + r, "num_vehicles")
    equipment_type = config.get("reservation_" + r, "equipment_type")
    sites = ast.literal_eval(config.get("reservation_" + r, "sites"))

    available_sites = find_available_sites(driver, sites, arrival, length)
    if available_sites:
      print('Sites available for reservation %d: %s' % (count, available_sites))
    else:
      print('No sites available for reservation %d.' % count)

  
if __name__ == '__main__':
  sys.exit(main(sys.argv))


def hold(driver, trip):
  # Click book button
  driver.find_element_by_id('btnbookdates').click()

  # Check to see if we got an error, if so refresh
  WebDriverWait(driver, 5).until(
      EC.presence_of_element_located((By.CSS_SELECTOR, '#contentArea')))
  if (not check_errors()):
    # Enter username
    username_field = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located(
          (By.CSS_SELECTOR, '#emailGroup input')))
    username_field.send_keys(USERNAME);

    # Enter password
    password_field = driver.find_element_by_css_selector(
        '#passwrdGroup input')
    password_field.send_keys(PASSWORD);

    # Click login button
    driver.find_element_by_name('submitForm').click()

    # Check if Primary Equipment field is readonly, if not set a value
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'equip')))
    if driver.find_element_by_id('equip').is_enabled():
      driver.find_element_by_css_selector(
          "select#equip > option[value='" + EQUIPMENT_TYPE + "']").click()

    driver.find_element_by_id('numoccupants').send_keys(NUM_OCCUPANTS)
    driver.find_element_by_id('numvehicles').send_keys(NUM_VEHICLES)

    # Click "Yes, I have read and understood this important information"
    driver.find_element_by_id('agreement').click()

    # Click "Continue to Shopping Cart" button
    driver.find_element_by_id('continueshop').click()

    print('You have 15 minutes to complete this reservation in the browser '
          'window.')

def check_errors(driver):
  try:
    error = driver.find_element_by_css_selector('#msg1')
    if error:
      logger.warning('Found error in site: ' + error.text)
      return True
  except Exception as e:
    logger.warning('Error while getting #mgs1: ' + str(e))

  return False
