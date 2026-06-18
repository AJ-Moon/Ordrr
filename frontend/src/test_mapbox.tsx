import React from 'react';
import { SearchBox } from '@mapbox/search-js-react';
export default function Test() {
  return <SearchBox accessToken="pk.123" onRetrieve={(res) => console.log(res)} />;
}
